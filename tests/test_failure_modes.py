"""اختبارات حالات الفشل (T7).

القاعدة: النتائج ثابتة (سيناريوهات بتاريخ محدد) فممكن نتحقق منها مباشرة —
وهي نفسها الأرقام المكتوبة بـ docs/failure_modes.md.
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.api import main as api
from src.eval import failure_modes as fm


def _by_id():
    return {c["id"]: c for c in fm.run_all()["cases"]}


# ----------------------------------------------------------------- السكربت
def test_six_cases_run_with_actual_results():
    payload = fm.run_all()
    assert payload["n_cases"] == 6
    assert [c["id"] for c in payload["cases"]] == ["FM1", "FM2", "FM3", "FM4", "FM5", "FM6"]
    for case in payload["cases"]:
        r = case["result"]
        assert r["decision"] in ("allow", "warn", "hold")
        assert 0 <= r["score"] <= 100
        assert r["rules_version"] == "v1"
        assert case["verdict_ar"]
        assert case["description_ar"]


def test_results_are_deterministic():
    """نفس السيناريوهات => نفس النتيجة بالضبط بين تشغيلين."""
    assert fm.run_all() == fm.run_all()


def test_engine_inputs_contain_no_ground_truth():
    """المدخلات (history + tx) ما فيها is_scam / scam_type / case_id إطلاقاً."""
    banned = {"is_scam", "scam_type", "case_id"}
    for factory in fm.CASES:
        case = factory()
        for row in case["history"]:
            assert not banned & set(row), case["id"]
        assert not banned & set(case["tx"]), case["id"]


# ----------------------------------------------------------------- الحالات
def test_fm1_false_positive_on_routine_family_transfer():
    c = _by_id()["FM1"]
    assert c["reality"] == "legit"
    assert c["result"]["decision"] == "warn"
    assert c["result"]["score"] == 45
    ids = [r["rule_id"] for r in c["result"]["reasons"]]
    assert ids == ["AMOUNT_HIGH", "NEW_RECIPIENT"]
    assert c["verdict_ar"] == "إنذار كاذب"


def test_fm2_evades_rapid_sequence_and_is_missed():
    c = _by_id()["FM2"]
    ids = [r["rule_id"] for r in c["result"]["reasons"]]
    assert "RAPID_SEQUENCE" not in ids          # التحايل المخطط نجح
    assert c["result"]["decision"] == "allow"   # ومع ذلك فات (20 < 30)
    assert c["verdict_ar"] == "اختراق: احتيال فات"
    # القاعدة البطيئة انطبقت لكن وزنها ما وصل عتبة التنبيه — هذا هو الخلل المكشوف
    assert "CUMULATIVE_NEW_RECIPIENT" in ids
    assert c["result"]["score"] == 20


def test_fm3_legit_new_recipient_holds():
    c = _by_id()["FM3"]
    assert c["reality"] == "legit"
    assert c["result"]["decision"] == "hold"
    assert c["result"]["score"] == 60
    ids = [r["rule_id"] for r in c["result"]["reasons"]]
    assert ids == ["AMOUNT_HIGH", "NEW_RECIPIENT", "BALANCE_DRAIN"]
    assert c["verdict_ar"] == "إنذار كاذب"


def test_fm4_silent_fraud_is_missed():
    c = _by_id()["FM4"]
    assert c["reality"] == "scam"
    assert c["result"]["decision"] == "allow"
    assert c["result"]["score"] == 0
    ids = [r["rule_id"] for r in c["result"]["reasons"]]
    assert ids == ["TRUSTED_RECIPIENT"]          # الثقة طمرت أي إشارة
    assert c["verdict_ar"] == "اختراق: احتيال فات"


def test_fm5_prompt_injection_does_not_downgrade():
    c = _by_id()["FM5"]
    assert c["reality"] == "scam"
    assert c["result"]["matched_pattern"] == "prize_fee"
    assert c["result"]["decision"] == "hold"
    assert c["result"]["score"] == 95            # حقن ما نقص ولا نقطة
    assert c["verdict_ar"] == "كشف صحيح"


def test_fm6_dialect_misses_keywords():
    c = _by_id()["FM6"]
    assert c["reality"] == "scam"
    assert c["result"]["matched_pattern"] is None  # الكتالوج ما فهم اللهجة
    assert c["result"]["decision"] == "allow"      # ومبلغ صغير = فات
    assert c["verdict_ar"] == "اختراق: احتيال فات"


# ----------------------------------------------------------------- كتابة الملف
def test_main_writes_json(tmp_path, monkeypatch):
    out = tmp_path / "failure_modes_run.json"
    monkeypatch.setattr(fm, "RUN_PATH", out)
    assert fm.main() == 0
    raw = out.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["n_cases"] == 6
    assert data["generated_at"]
    assert data["rules_version"] == "v1"
    assert "إنذار كاذب" in raw  # العربي سليم UTF-8 بملف فعلي


# ----------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path, monkeypatch):
    """عميل TestClient خفيف (النقطة تقرأ ملف JSON بس)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(api, "get_connection", lambda: __import__(
        "src.db", fromlist=["get_connection"]).get_connection(db_path))
    monkeypatch.setattr(api, "init_db", lambda *a, **k: __import__(
        "src.db", fromlist=["init_db"]).init_db(db_path))
    monkeypatch.setattr(api, "EXPORT_DIR", tmp_path / "logs")
    monkeypatch.setattr(api, "EVAL_RESULTS_PATH", tmp_path / "eval_results.json")
    monkeypatch.setattr(api, "_CATALOGUE", None)

    with TestClient(api.app) as c:
        yield c


def test_failure_modes_endpoint_returns_actual_cases(client):
    """الملف موجود بالمشروع => صفحة النتائج تعرض الحالات الستة."""
    res = client.get("/api/failure_modes")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert data["n_cases"] == 6
    assert data["cases"][0]["id"] == "FM1"
    assert data["cases"][0]["result"]["decision"] == "warn"
    assert data["cases"][0]["verdict_ar"] == "إنذار كاذب"


def test_failure_modes_endpoint_missing_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "FAILURE_MODES_PATH", tmp_path / "nope.json")
    res = client.get("/api/failure_modes")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False
    assert data["cases"] == []
    assert "failure_modes" in data["hint_ar"]
