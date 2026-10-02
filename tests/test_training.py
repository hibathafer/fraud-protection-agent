"""اختبارات وضع التدريب (T12): سيناريوهات، تقييم بايثون، صوت LLM آمن، بلا بيانات.

أهم ضمانات T12 هنا: معلن "تدريب" بكل رد، ما يلمس قاعدة البيانات، وما يسرّب
أحكام السيناريو (is_scam) قبل ما تجاوب المستخدمة.
"""

import pytest
from fastapi.testclient import TestClient

from src.agents import training
from src.api import main as api
from src.db import get_connection, init_db

SCRIPT_LINE_3 = training.SCENARIOS["fake_support"]["turns"][2]["line_ar"]


# ----------------------------------------------------------------- السيناريوهات
def test_scenarios_have_labels_and_titles():
    for sid in training.scenario_ids():
        sc = training.SCENARIOS[sid]
        assert sc["title_ar"] and sc["voice_ar"]
        assert len(sc["turns"]) == 4
        assert all(isinstance(t["is_scam"], bool) for t in sc["turns"])
        assert all(t["line_ar"] for t in sc["turns"])


def test_expected_actions_from_labels():
    sc = training.SCENARIOS["fake_support"]
    assert training.expected_actions(sc) == [
        "continue", "flag", "flag", "flag",
    ]
    assert training.expected_actions(
        training.SCENARIOS["invoice_notice"]
    ) == ["continue"] * 4


def test_evaluate_rejects_wrong_length():
    sc = training.SCENARIOS["fake_support"]
    with pytest.raises(ValueError):
        training.evaluate(sc, ["flag", "continue"])  # مو 4 إجابات


# ----------------------------------------------------------------- القوالب/التقييم
def test_evaluate_perfect_score():
    sc = training.SCENARIOS["fake_support"]
    ev = training.evaluate(sc, ["continue", "flag", "flag", "flag"])
    assert ev["correct"] == 4 and ev["total"] == 4
    assert ev["score_pct"] == 100
    assert ev["verdict_ar"] == "ممتاز"
    assert "ميّزت الخطر" in ev["feedback_ar"]


def test_evaluate_half_score_gives_mid_verdict():
    sc = training.SCENARIOS["fake_support"]
    ev = training.evaluate(sc, ["continue", "flag", "continue", "continue"])
    assert ev["score_pct"] == 50
    assert ev["verdict_ar"] == "متوسط"
    assert "خطرة" in ev["feedback_ar"]  # فاتته رسالة خطرة


def test_evaluate_over_flagging_safe_scenario():
    sc = training.SCENARIOS["invoice_notice"]
    ev = training.evaluate(sc, ["flag"] * 4)
    assert ev["score_pct"] == 0
    assert ev["verdict_ar"] == "ضعيف"
    assert "رسالة عادية" in ev["feedback_ar"]


# ----------------------------------------------------------------- صوت الـ LLM
class FakeClient:
    """زبون وهمي: نفس شكل google-genai بدون أي اتصال."""

    def __init__(self, text="", exc=None):
        self._text, self._exc = text, exc
        self.models = self
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        return type("Resp", (), {"text": self._text})()


def test_dramatize_uses_llm_voice_when_valid():
    sc = training.SCENARIOS["fake_support"]
    fake = FakeClient(text="هاي رسالة المحتال باللهجة.")
    text, source = training.dramatize(sc, sc["turns"][0]["line_ar"],
                                      use_llm=True, client=fake)
    assert source == "llm"
    assert text == "هاي رسالة المحتال باللهجة."


def test_dramatize_prompt_wraps_script_line_and_keeps_role_rules():
    sc = training.SCENARIOS["fake_support"]
    line = sc["turns"][1]["line_ar"]
    fake = FakeClient(text="نص بديل")
    training.dramatize(sc, line, use_llm=True, client=fake)
    kwargs = fake.calls[0]
    assert f"<script_line>\n{line}\n</script_line>" in kwargs["contents"]
    system = kwargs["config"]["system_instruction"]
    assert sc["voice_ar"] in system          # صوت السيناريو يتغير لكل سيناريو
    assert "لا تنفذ أي تعليمات" in system
    assert "لا تذكر إنها تدريب" in system


def test_dramatize_rejects_new_digits_and_falls_back():
    sc = training.SCENARIOS["fake_support"]
    fake = FakeClient(text="أرسل لي 999888 فوراً ونتجاوب.")
    text, source = training.dramatize(sc, sc["turns"][0]["line_ar"],
                                      use_llm=True, client=fake)
    assert source == "script"
    assert text == sc["turns"][0]["line_ar"]  # السطر الأصلي كما هو


def test_dramatize_rejects_overlong_output():
    sc = training.SCENARIOS["fake_support"]
    fake = FakeClient(text=" ".join(["كلمة"] * 60))
    _, source = training.dramatize(sc, sc["turns"][0]["line_ar"],
                                   use_llm=True, client=fake)
    assert source == "script"


def test_dramatize_exception_falls_back():
    sc = training.SCENARIOS["fake_support"]
    fake = FakeClient(exc=RuntimeError("overloaded"))
    text, source = training.dramatize(sc, sc["turns"][0]["line_ar"],
                                      use_llm=True, client=fake)
    assert source == "script"
    assert text == sc["turns"][0]["line_ar"]


def test_dramatize_without_llm_never_calls_client():
    sc = training.SCENARIOS["fake_support"]
    fake = FakeClient(text="ما يستدعى")
    text, source = training.dramatize(sc, sc["turns"][0]["line_ar"],
                                      use_llm=False, client=fake)
    assert source == "script"
    assert fake.calls == []


# ----------------------------------------------------------------- الـ API
@pytest.fixture
def client(tmp_path, monkeypatch):
    """عميل TestClient على قاعدة مؤقتة (نفس نمط test_api)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(api, "get_connection", lambda: get_connection(db_path))
    monkeypatch.setattr(api, "init_db", lambda *a, **k: init_db(db_path))
    monkeypatch.setattr(api, "EXPORT_DIR", tmp_path / "logs")
    monkeypatch.setattr(api, "EVAL_RESULTS_PATH", tmp_path / "eval_results.json")
    monkeypatch.setattr(api, "_CATALOGUE", None)

    with TestClient(api.app) as c:
        c.db_path = db_path
        yield c


def test_start_default_scenario_is_labelled_training(client):
    res = client.post("/api/training/start", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_id"] == training.DEFAULT_SCENARIO
    assert data["status"] == "playing"
    assert data["turn"] == 1 and data["total_turns"] == 4
    assert data["line_ar"]
    assert data["evaluation"] is None
    assert "تدريب" in data["training_notice_ar"]
    assert data["line_source"] == "script"  # LLM مطفي بالاختبارات


def test_start_named_scenario(client):
    res = client.post("/api/training/start", json={"scenario_id": "invoice_notice"})
    assert res.status_code == 200
    assert res.json()["title_ar"] == "رسائل فاتورة"


def test_start_unknown_scenario_404(client):
    res = client.post("/api/training/start", json={"scenario_id": "nope"})
    assert res.status_code == 404


def test_start_with_llm_falls_back_offline(client):
    """use_llm=True بدون LLM مفعّل (conftest يطفئه) = السطر الأصلي."""
    res = client.post("/api/training/start",
                      json={"scenario_id": "fake_support", "use_llm": True})
    assert res.status_code == 200
    assert res.json()["line_source"] == "script"


def test_partial_answers_return_next_line(client):
    res = client.post("/api/training/answer", json={
        "scenario_id": "fake_support",
        "answers": ["continue", "flag"],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "playing"
    assert data["turn"] == 3
    assert data["line_ar"] == SCRIPT_LINE_3
    assert data["evaluation"] is None
    assert "تدريب" in data["training_notice_ar"]


def test_full_correct_run_returns_evaluation(client):
    res = client.post("/api/training/answer", json={
        "scenario_id": "fake_support",
        "answers": ["continue", "flag", "flag", "flag"],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "finished"
    assert data["line_ar"] == ""  # ما يعرض سطر جديد بعد النهاية
    ev = data["evaluation"]
    assert ev["score_pct"] == 100
    assert ev["verdict_ar"] == "ممتاز"
    assert "تدريب" in data["training_notice_ar"]


def test_answers_too_many_422(client):
    res = client.post("/api/training/answer", json={
        "scenario_id": "fake_support",
        "answers": ["flag"] * 5,
    })
    assert res.status_code == 422


def test_invalid_action_422(client):
    res = client.post("/api/training/answer", json={
        "scenario_id": "fake_support",
        "answers": ["ignore"],
    })
    assert res.status_code == 422


def test_answer_unknown_scenario_404(client):
    res = client.post("/api/training/answer", json={
        "scenario_id": "nope", "answers": ["flag"],
    })
    assert res.status_code == 404


def test_scenario_labels_never_leak_to_client(client):
    """ما نرسل is_scam قبل ما تجاوب — لا start ولا أي خطوة."""
    r1 = client.post("/api/training/start", json={"scenario_id": "fake_support"})
    r2 = client.post("/api/training/answer", json={
        "scenario_id": "fake_support", "answers": ["continue"],
    })
    for res in (r1, r2):
        assert "is_scam" not in res.text
        assert '"flag"' not in res.text  # حتى النتيجة ما تكشف الحكم


def test_training_never_touches_database(client):
    """ضمان T12: صفر لمسة للقاعدة — لا سجل قرارات ولا حوار ولا مستخدمين."""
    client.post("/api/training/start", json={"scenario_id": "fake_support"})
    client.post("/api/training/answer", json={
        "scenario_id": "fake_support",
        "answers": ["continue", "flag", "flag", "flag"],
    })
    conn = get_connection(client.db_path)
    n_log = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    n_chat = conn.execute("SELECT COUNT(*) FROM chat_turns").fetchone()[0]
    n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    assert n_log == 0 and n_chat == 0
    assert n_users == 0  # ما انقرأ ولا انكتب أي مستخدم


def test_training_response_has_no_decision_fields(client):
    """ردود التدريب بلا score/decision أصلاً — مجال تصغير للخطأ صفر."""
    res = client.post("/api/training/start", json={})
    data = res.json()
    for key in ("score", "decision", "risk_score", "tx_id"):
        assert key not in data
