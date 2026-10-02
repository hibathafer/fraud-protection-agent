"""اختبارات تكامل محفظة Zain Cash (T5b): اعتراض التحويل قبل التنفيذ.

المسار المطلوب:
    طلب التحويل → كشف + توعية → allow: تنفيذ وإيصال
                                 warn/hold: تعليق + فترة تهدئة + /api/choice

كل الاختبارات على قاعدة مؤقتة (tmp): ما نلمس data/fraud.db.
"""

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api import main as api
from src.db import USER_FIELDS, get_connection, init_db
from src.integrations import wallet_flow

NOW = "2026-10-20T14:00:00+03:00"


def at(days_ago=0, hour=14, minute=0):
    dt = datetime.fromisoformat(NOW) - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=minute, second=0).isoformat()


# ----------------------------------------------------------------- قاعدة الاختبار
@pytest.fixture
def client(tmp_path, monkeypatch):
    """عميل TestClient على قاعدة مؤقتة فيها مستخدمان وتاريخ معروف."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(api, "get_connection", lambda: get_connection(db_path))
    monkeypatch.setattr(api, "init_db", lambda *a, **k: init_db(db_path))
    monkeypatch.setattr(api, "EXPORT_DIR", tmp_path / "logs")
    monkeypatch.setattr(api, "EVAL_RESULTS_PATH", tmp_path / "eval_results.json")
    monkeypatch.setattr(api, "_CATALOGUE", None)
    wallet_flow.clear_pending()

    conn = get_connection(db_path)
    users = [
        {"user_id": "u01", "name": "سالم", "archetype": "موظف براتب", "split": "dev"},
        {"user_id": "u02", "name": "هدى", "archetype": "طالب", "split": "dev"},
        {"user_id": "t01", "name": "مستخدم معزول", "archetype": "تاجر صغير", "split": "test"},
    ]
    conn.executemany(
        f"INSERT INTO users({','.join(USER_FIELDS)}) VALUES({','.join('?' * len(USER_FIELDS))})",
        [[u[k] for k in USER_FIELDS] for u in users],
    )
    txs = []
    for i in range(12):
        txs.append({
            "tx_id": f"tx{i:03d}", "user_id": "u01", "ts": at(days_ago=30 + i),
            "amount_iqd": 100_000, "balance_before_iqd": 3_000_000, "tx_type": "transfer",
            "recipient_id": "r_old", "recipient_age_days": 500, "note": None,
            "context_message": None, "is_scam": 0, "scam_type": None, "case_id": None,
        })
    conn.executemany(
        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [list(t.values()) for t in txs]
    )
    conn.commit()
    conn.close()

    with TestClient(api.app) as c:
        c.db_path = db_path
        yield c
    wallet_flow.clear_pending()


def wallet_body(**kw):
    """طلب تحويل عادي: مبلغ معتاد لمستلم جديد."""
    body = {
        "sender_msisdn": "07812345678",
        "recipient_msisdn": "07855550001",
        "amount_iqd": 100_000,
        "pin": "1234",
        "user_id": "u01",
    }
    body.update(kw)
    return body


def scam_wallet_body(**kw):
    """طلب تحويل يحمل نمط احتيال معروف (رسوم جائزة)."""
    body = wallet_body(
        amount_iqd=750_000,
        recipient_msisdn="07855559999",
        recipient_age_days=2,
        note="رسوم استلام الجائزة",
        context_message="مبروك ربحت سحب المحفظة، حول الرسوم حتى نرسلك الجائزة",
    )
    body.update(kw)
    return body


def log_row(client, tx_id):
    conn = get_connection(client.db_path)
    try:
        row = conn.execute("SELECT * FROM decision_log WHERE tx_id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ----------------------------------------------------------------- allow → تنفيذ
def test_wallet_allow_executes_transfer_and_returns_receipt(client):
    res = client.post("/api/wallet/transfer", json=wallet_body())
    assert res.status_code == 200, res.text
    data = res.json()

    # القرار من القواعد: مبلغ معتاد + ملاحظة عادية = allow (نقاط 20 للمستلم الجديد)
    assert data["decision"] == "allow"
    assert data["status"] == "executed"
    assert data["receipt"]["status"] == "success"
    assert data["receipt"]["receipt_id"].startswith("ZC")
    assert data["receipt"]["amount_iqd"] == 100_000
    # الإيصال ما يكشف الرقم كامل
    assert data["receipt"]["recipient_msisdn_masked"] == "0785****001"
    assert data["cooling_off_seconds"] is None
    assert data["final_status"] == "completed"

    row = log_row(client, data["tx_id"])
    assert row["decision"] == "allow"
    assert row["final_status"] == "completed"
    assert json.loads(row["receipt_json"])["receipt_id"] == data["receipt"]["receipt_id"]


# ----------------------------------------------------------------- warn/hold → تعليق
def test_wallet_scam_blocks_with_cooling_off_and_logs_pending(client):
    res = client.post("/api/wallet/transfer", json=scam_wallet_body())
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["decision"] == "hold"
    assert data["matched_pattern"] == "prize_fee"
    assert data["status"] == "blocked"          # ما نفذنا التحويل
    assert data["receipt"] is None
    assert data["cooling_off_seconds"] == 10    # فترة التهدئة المطلوبة
    assert data["final_status"] == "pending"

    row = log_row(client, data["tx_id"])
    assert row["decision"] == "hold"
    assert row["final_status"] == "pending"
    assert row["receipt_json"] is None
    assert row["user_choice"] is None
    assert wallet_flow.pending_count() == 1     # التحويل معلّق بانتظار /api/choice


def test_wallet_warn_also_blocks_with_cooling_off(client):
    """حتى التنبيه (warn) يوقف التحويل مؤقتاً بفترة تهدئة."""
    data = client.post("/api/wallet/transfer", json=wallet_body(
        amount_iqd=400_000, recipient_msisdn="07855550002")).json()
    assert data["decision"] == "warn"
    assert data["status"] == "blocked"
    assert data["cooling_off_seconds"] == 10
    assert data["final_status"] == "pending"


def test_wallet_choice_continue_executes_blocked_transfer(client):
    data = client.post("/api/wallet/transfer", json=scam_wallet_body()).json()
    assert data["status"] == "blocked"

    res = client.post("/api/choice", json={
        "tx_id": data["tx_id"], "choice": "continue",
        "recipient_id": "07855559999",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["receipt"] is not None
    assert body["receipt"]["status"] == "success"
    assert body["receipt"]["receipt_id"].startswith("ZC")
    assert body["final_status"] == "completed"
    assert body["user_choice"] == "continue"
    assert body["trusted_added"] is True  # المستلم الجديد دخل الموثوقين
    assert "الإيصال" in body["message_ar"]
    assert wallet_flow.pending_count() == 0

    row = log_row(client, data["tx_id"])
    assert row["user_choice"] == "continue"
    assert row["final_status"] == "completed"
    assert json.loads(row["receipt_json"])["status"] == "success"


def test_wallet_choice_cancel_cancels_and_keeps_no_receipt(client):
    data = client.post("/api/wallet/transfer", json=scam_wallet_body()).json()
    res = client.post("/api/choice", json={
        "tx_id": data["tx_id"], "choice": "cancel", "recipient_id": "07855559999"})
    assert res.status_code == 200
    body = res.json()
    assert body["receipt"] is None
    assert body["final_status"] == "cancelled"
    assert wallet_flow.pending_count() == 0

    row = log_row(client, data["tx_id"])
    assert row["user_choice"] == "cancel"
    assert row["final_status"] == "cancelled"
    assert row["receipt_json"] is None


# ----------------------------------------------------------------- خصوصية الـ pin
def test_wallet_pin_is_never_logged_nor_returned(client):
    pin = "987654"
    res = client.post("/api/wallet/transfer", json=scam_wallet_body(pin=pin))
    assert res.status_code == 200
    assert pin not in res.text          # الـ pin ما يرجع بالرد
    assert '"pin"' not in res.text

    data = res.json()
    row = log_row(client, data["tx_id"])
    assert pin not in (row["reasons_json"] or "")
    assert pin not in (row["coaching_message"] or "")
    assert row["receipt_json"] is None

    # بعد التنفيذ: الإيصال كمان ما يحمل الـ pin
    client.post("/api/choice", json={"tx_id": data["tx_id"], "choice": "continue"})
    receipt = json.loads(log_row(client, data["tx_id"])["receipt_json"])
    assert "pin" not in receipt
    assert pin not in [str(v) for v in receipt.values()]


def test_wallet_receipt_has_no_full_msisdn(client):
    data = client.post("/api/wallet/transfer", json=wallet_body()).json()
    receipt = data["receipt"]
    assert receipt["sender_msisdn_masked"] == "0781****678"
    assert "07812345678" not in [str(v) for v in receipt.values()]
    assert "07855550001" not in [str(v) for v in receipt.values()]


# ----------------------------------------------------------------- مدخلات خاطئة
def test_wallet_rejects_bad_msisdn_and_pin(client):
    bad_sender = client.post("/api/wallet/transfer", json=wallet_body(sender_msisdn="12345"))
    assert bad_sender.status_code == 422

    bad_recipient = client.post("/api/wallet/transfer", json=wallet_body(recipient_msisdn="07X"))
    assert bad_recipient.status_code == 422

    bad_pin = client.post("/api/wallet/transfer", json=wallet_body(pin="12"))
    assert bad_pin.status_code == 422

    same_party = client.post("/api/wallet/transfer", json=wallet_body(
        recipient_msisdn="07812345678"))
    assert same_party.status_code == 422


def test_wallet_rejects_ground_truth_fields(client):
    body = scam_wallet_body(is_scam=1, case_id="c1")
    res = client.post("/api/wallet/transfer", json=body)
    assert res.status_code == 422
    assert res.json()["detail"][0]["type"] == "extra_forbidden"


def test_wallet_unknown_user_returns_404(client):
    res = client.post("/api/wallet/transfer", json=wallet_body(user_id="uXX"))
    assert res.status_code == 404


# ----------------------------------------------------------------- ملف مؤقت + قواعد
def test_wallet_without_user_uses_temporary_profile(client):
    """بدون user_id: ملف مؤقت بدون تاريخ — يشتغل ويسجّل بلا مستخدم."""
    res = client.post("/api/wallet/transfer", json=wallet_body(
        user_id=None, amount_iqd=50_000, ts=NOW))
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "executed"
    assert data["decision"] == "allow"
    assert data["user_id"] is None
    assert log_row(client, data["tx_id"])["user_id"] is None


def test_wallet_decision_comes_from_rules_only(client):
    """القرار من القواعد والتوعية قوالب — الـ LLM ما يدخل أبداً."""
    data = client.post("/api/wallet/transfer", json=scam_wallet_body(use_llm=False)).json()
    assert data["decision"] == "hold"
    assert data["score"] >= 60
    assert data["coaching_source"] == "template"
    assert data["rules_version"] == "v1"
    assert any(r["rule_id"] == "SCAM_PATTERN" for r in data["reasons"])


# ----------------------------------------------------------------- التوافق مع المسار القديم
def test_regular_assess_choice_sets_final_status_without_receipt(client):
    """اختيار /api/assess العادي: final_status يتسجّل بدون إيصال."""
    assess = client.post("/api/assess", json={
        "user_id": "u01",
        "transaction": {"amount_iqd": 750_000, "recipient_id": "r_scam1",
                        "recipient_age_days": 2, "note": "رسوم",
                        "context_message": "مبروك ربحت الجائزة، حول الرسوم لتستلمها"},
    }).json()
    res = client.post("/api/choice", json={"tx_id": assess["tx_id"], "choice": "cancel"})
    body = res.json()
    assert body["final_status"] == "cancelled"
    assert body["receipt"] is None
    row = log_row(client, assess["tx_id"])
    assert row["final_status"] == "cancelled"
    assert row["receipt_json"] is None
    assert wallet_flow.pending_count() == 0
