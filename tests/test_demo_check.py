"""اختبارات سكربت فحص الديمو (T10).

كلها وهمية: صفر subprocess فعلي، صفر إنترنت، صفر مفتاح — الأدوات تُحقن
(runner/client/rewrite) حتى يبقى الاتصال الحقيقي لـ demo_check مسؤولية
التشغيل اليدوي من عند هبو.
"""

from src import config, demo_check
from src.coaching import llm


class FakeRes:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


class FakeClient:
    """عميل TestClient وهمي: routes = {path: FakeRes}."""

    def __init__(self, routes):
        self.routes = routes

    def get(self, path):
        return self.routes[path]


# ----------------------------------------------------------------- سطر النتيجة
def test_line_prints_pass_and_fail(capsys):
    assert demo_check._line("database", True, "users=20") is True
    assert "PASS database - users=20" in capsys.readouterr().out

    assert demo_check._line("database", False, "users=0") is False
    assert "FAIL database" in capsys.readouterr().out


# ----------------------------------------------------------------- قاعدة البيانات
def test_check_database_ok():
    client = FakeClient({"/api/users": FakeRes(200, {"count": 20})})
    ok, detail = demo_check.check_database(client)
    assert ok is True
    assert "users=20" in detail


def test_check_database_fails_without_users():
    client = FakeClient({"/api/users": FakeRes(404, {"detail": "x"})})
    ok, _ = demo_check.check_database(client)
    assert ok is False


# ----------------------------------------------------------------- الاختبارات
def test_check_tests_uses_injected_runner_not_subprocess():
    ok, tail = demo_check.check_tests(runner=lambda: (True, "213 passed in 21.0s"))
    assert ok is True
    assert "213 passed" in tail

    ok, tail = demo_check.check_tests(runner=lambda: (False, "1 failed"))
    assert ok is False
    assert "failed" in tail


# ----------------------------------------------------------------- المفتاح
def test_check_api_key_present(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "llm")
    monkeypatch.setattr(llm, "load_api_key", lambda: "test-key")
    ok, detail = demo_check.check_api_key()
    assert ok is True
    assert "mode=llm" in detail and "key=present" in detail
    assert "test-key" not in detail  # المفتاح ما ينطبع أبداً


def test_check_api_key_missing(monkeypatch):
    monkeypatch.setattr(llm, "load_api_key", lambda: None)
    ok, detail = demo_check.check_api_key()
    assert ok is False
    assert "key=missing" in detail


# ----------------------------------------------------------------- اتصال Gemini
def test_gemini_fails_in_template_mode(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "template")
    ok, detail = demo_check.check_gemini_connection()
    assert ok is False
    assert "COACH_MODE=llm" in detail  # يوضّح وش تسوي


def test_gemini_fails_without_key(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "llm")
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: None)
    ok, detail = demo_check.check_gemini_connection()
    assert ok is False
    assert "GEMINI_API_KEY" in detail


def test_gemini_success_reports_latency(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "llm")
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: "test-key")
    monkeypatch.setattr(demo_check, "_ping_model", lambda key: "هاي أول مرة تحوّل، لا تعطي الرمز.")
    ok, detail = demo_check.check_gemini_connection()
    assert ok is True
    assert "latency=" in detail and "model=" in detail


def test_gemini_fails_when_reply_empty(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "llm")
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: "test-key")
    monkeypatch.setattr(demo_check, "_ping_model", lambda key: "")
    ok, detail = demo_check.check_gemini_connection()
    assert ok is False
    assert "empty reply" in detail


def test_gemini_shows_real_error_without_leaking_key(monkeypatch):
    """الخطأ الحقيقي ينعرض (مفيد للتشخيص) بدون ما يطيح المفتاح."""
    monkeypatch.setenv("COACH_MODE", "llm")
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: "SECRET-KEY-123")

    def _boom(key):
        raise RuntimeError("503 UNAVAILABLE ... key=SECRET-KEY-123")

    monkeypatch.setattr(demo_check, "_ping_model", _boom)
    ok, detail = demo_check.check_gemini_connection()
    assert ok is False
    assert "error=" in detail and "503 UNAVAILABLE" in detail
    assert "SECRET-KEY-123" not in detail
    assert "***" in detail


# ----------------------------------------------------------------- fallback
def test_fallback_check_works_offline():
    """حقيقي بس بدون نت: عميل مكسور + use_llm=False = القالب دائماً."""
    ok, detail = demo_check.check_fallback()
    assert ok is True
    assert "template" in detail


# ----------------------------------------------------------------- سيناريوهات demo
def _write(path, data):
    path.write_text(
        __import__("json").dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def test_load_demo_files_accepts_all_three_kinds(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    _write(tmp_path / "a_wallet.json",
           {"name_ar": "عادي", "payload": {"user_id": "u01", "transaction": {}}})
    _write(tmp_path / "b_history.json",
           {"name_ar": "بطيء", "payload": {"history": [{}, {}, {}], "transaction": {}}})
    _write(tmp_path / "c_text.json",
           {"name_ar": "نص حر", "payload": {"text": "حول مية ألف"}})

    count, problems = demo_check.load_demo_files()
    assert count == 3
    assert problems == []


def test_load_demo_files_reports_bad_json(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    count, problems = demo_check.load_demo_files()
    assert count == 1
    assert problems and "broken.json" in problems[0]


def test_load_demo_files_reports_payload_without_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    _write(tmp_path / "weird.json", {"name_ar": "غريب", "payload": {"foo": 1}})
    count, problems = demo_check.load_demo_files()
    assert problems and "no user_id/history/text" in problems[0]


def test_check_demo_scenarios_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    for i in range(6):
        _write(tmp_path / f"s{i}.json",
               {"name_ar": f"سيناريو {i}", "payload": {"user_id": "u01"}})
    client = FakeClient({"/api/demo_scenarios": FakeRes(200, {"count": 6})})
    ok, detail = demo_check.check_demo_scenarios(client)
    assert ok is True
    assert "files=6" in detail and "endpoint=6" in detail


def test_check_demo_scenarios_fails_when_too_few(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    _write(tmp_path / "solo.json", {"name_ar": "وحيد", "payload": {"user_id": "u01"}})
    client = FakeClient({"/api/demo_scenarios": FakeRes(200, {"count": 1})})
    ok, _ = demo_check.check_demo_scenarios(client)
    assert ok is False


def test_check_demo_scenarios_fails_on_endpoint_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(demo_check, "DEMO_DIR", tmp_path)
    for i in range(6):
        _write(tmp_path / f"s{i}.json",
               {"name_ar": f"سيناريو {i}", "payload": {"user_id": "u01"}})
    # endpoint ما يشوف نفس عدد الملفات = مشكلة تحميل
    client = FakeClient({"/api/demo_scenarios": FakeRes(200, {"count": 3})})
    ok, _ = demo_check.check_demo_scenarios(client)
    assert ok is False
