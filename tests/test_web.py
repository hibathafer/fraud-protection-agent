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


def test_demo_scenarios_endpoint(client):
    res = client.get("/api/demo_scenarios")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 3
    assert len(data["scenarios"]) >= 3
    # كل سيناريو لازم يكون له name_ar و payload
    for s in data["scenarios"]:
        assert "name_ar" in s
        assert "payload" in s
        assert "user_id" in s["payload"] or "history" in s["payload"]


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
