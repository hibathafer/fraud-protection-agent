"""اختبارات صفحات الويب (T5).

الصفحات لازم ترجع 200 وتحتوي على المحتوى الأساسي.
"""

import pytest
from fastapi.testclient import TestClient

from src.api import main as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    """عميل TestClient على قاعدة مؤقتة."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(api, "get_connection", lambda: __import__("src.db", fromlist=["get_connection"]).get_connection(db_path))
    monkeypatch.setattr(api, "init_db", lambda *a, **k: __import__("src.db", fromlist=["init_db"]).init_db(db_path))
    monkeypatch.setattr(api, "EXPORT_DIR", tmp_path / "logs")
    monkeypatch.setattr(api, "EVAL_RESULTS_PATH", tmp_path / "eval_results.json")
    monkeypatch.setattr(api, "_CATALOGUE", None)

    with TestClient(api.app) as c:
        yield c


def test_index_page_returns_200(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "وكيل حماية من الاحتيال" in res.text


def test_log_page_returns_200(client):
    res = client.get("/log.html")
    assert res.status_code == 200
    assert "سجل القرارات" in res.text


def test_results_page_returns_200(client):
    res = client.get("/results.html")
    assert res.status_code == 200
    assert "نتائج التقييم" in res.text


def test_css_returns_200(client):
    res = client.get("/style.css")
    assert res.status_code == 200
    assert "phone-frame" in res.text


def test_js_returns_200(client):
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "loadUsers" in res.text


def test_index_has_free_text_box_for_intake(client):
    """صندوق النص الحر (T6) موجود بالصفحة ومعه صندوق سؤال التوضيح."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="scenarioText"' in res.text
    assert 'id="clarifyBox"' in res.text
    assert "سيناريو من الحكم" in res.text


def test_js_calls_scenario_text_endpoint(client):
    """واجهة الويب تتصل بـ /api/scenario_text عند فحص النص."""
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "/api/scenario_text" in res.text
    assert "submitScenarioText" in res.text


def test_results_page_links_failure_modes(client):
    """صفحة النتائج تعرض جدول حالات الفشل (T7) من /api/failure_modes."""
    assert client.get("/results.html").status_code == 200
    res = client.get("/app.js")
    assert "/api/failure_modes" in res.text
    assert "loadFailureModes" in res.text


def test_demo_scenarios_endpoint(client):
    res = client.get("/api/demo_scenarios")
    assert res.status_code == 200
    data = res.json()
    # T10: ستة سيناريوهات على الأقل (عادية، جائزة، حساب آمن، OTP، بطيء، نص حر)
    assert data["count"] >= 6
    assert len(data["scenarios"]) >= 6
    # كل سيناريو لازم يكون له name_ar و payload من أحد الأنواع الثلاثة
    for s in data["scenarios"]:
        assert "name_ar" in s
        assert "payload" in s
        assert (
            "user_id" in s["payload"]
            or "history" in s["payload"]
            or "text" in s["payload"]
        )


def test_demo_scenarios_have_valid_payload(client):
    """كل سيناريو لازم يكون له payload صالح."""
    res = client.get("/api/demo_scenarios")
    data = res.json()
    for s in data["scenarios"]:
        payload = s["payload"]
        if "user_id" in payload:
            assert payload["user_id"]
            assert "transaction" in payload
            assert "amount_iqd" in payload["transaction"]
            assert "recipient_id" in payload["transaction"]
        elif "history" in payload:
            # احتيال بطيء: تاريخ يدوي (3 تحويلات+) + المعاملة الحالية
            assert len(payload["history"]) >= 3
            assert payload["history"][0]["recipient_id"]
            assert "transaction" in payload
            assert "amount_iqd" in payload["transaction"]
        elif "text" in payload:
            # نص حر: جملة غير فارغة تفحصها صندوق Intake
            assert payload["text"].strip()
        else:
            raise AssertionError(f"payload بدون نوع معروف: {payload}")


def test_js_applies_all_scenario_kinds(client):
    """app.js يطبّق الأنواع الثلاثة: نص حر + تاريخ يدوي + محفظة (T10)."""
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "payload.text" in res.text          # نص حر → الصندوق + فحص فوري
    assert "payload.history" in res.text       # احتيال بطيء → /api/scenario
    assert "postScenario" in res.text          # دالة الإرسال للمستمع اليدوي
    assert "submitScenarioText" in res.text    # فحص النص الحر


def test_warning_modal_has_chat_box(client):
    """مربع الحوار (T11) موجود داخل نافذة التحذير."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="chatBox"' in res.text
    assert 'id="chatInput"' in res.text
    assert 'id="chatSendBtn"' in res.text


def test_js_posts_chat_messages(client):
    """app.js يرسل الرسائل لـ /api/chat بـ use_llm ويحترم حد الرسائل."""
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "/api/chat" in res.text
    assert "sendChat" in res.text
    assert "use_llm" in res.text
    assert "limit_reached" in res.text  # انوصل للحد: نقفل الإدخال


def test_training_box_present_and_labelled(client):
    """صندوق التدريب (T12) موجود ومعلن بوضوح بالواجهة."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="trainingBox"' in res.text
    assert 'id="trainingStartBtn"' in res.text
    assert 'id="flagBtn"' in res.text
    assert 'id="trainingContinueBtn"' in res.text
    assert "وضع تدريب" in res.text  # الوسم ظاهر للمستخدم


def test_js_calls_training_endpoints(client):
    """app.js ينادي نقاط التدريب ويعرض التقييم."""
    res = client.get("/app.js")
    assert res.status_code == 200
    assert "/api/training/start" in res.text
    assert "/api/training/answer" in res.text
    assert "startTraining" in res.text
    assert "answerTraining" in res.text
    assert "showTrainingResult" in res.text
