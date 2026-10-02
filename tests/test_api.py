"""اختبارات الـ API بـ TestClient (قسم 10 و17).

كل الاختبارات على قاعدة مؤقتة (tmp): ما نلمس data/fraud.db ولا بيانات المشروع.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import main as api
from src.db import USER_FIELDS, get_connection, init_db

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
        c.db_path = db_path  # نداءه بالاختبارات اللي تحتاج تفحص القاعدة
        yield c


def scam_body(**kw):
    body = {
        "user_id": "u01",
        "transaction": {
            "amount_iqd": 750_000,
            "recipient_id": "r_scam1",
            "recipient_age_days": 2,
            "note": "رسوم الاستلام",
            "context_message": "مبروك ربحت الجائزة، حول رسوم المعالجة لتستلمها",
        },
    }
    body.update(kw)
    return body


def log_row(client, tx_id):
    conn = get_connection(client.db_path)
    try:
        cur = conn.execute("SELECT * FROM decision_log WHERE tx_id = ?", (tx_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ----------------------------------------------------------------- GET /api/users
def test_users_endpoint_lists_dev_users_only(client):
    data = client.get("/api/users").json()
    ids = [u["user_id"] for u in data["users"]]
    assert data["count"] == 2
    assert ids == ["u01", "u02"]
    assert "t01" not in ids  # مستخدمو الاختبار المعزول ما ينكشفون
    assert data["users"][0]["n_tx"] == 12


def test_profile_endpoint_returns_stats(client):
    data = client.get("/api/users/u01/profile").json()
    assert data["user_id"] == "u01" and data["name"] == "سالم"
    # as_of = وقت آخر معاملة، والإحصاءات محسوبة قبلها (نفس قاعدة عدم التسريب 7.1)
    assert data["as_of"] == at(days_ago=30)
    assert data["profile"]["n_tx"] == 11
    assert data["profile"]["median_amount"] == 100_000
    assert data["profile"]["typical_hours"] == [14]


def test_unknown_user_returns_404(client):
    assert client.get("/api/users/uXX/profile").status_code == 404


# ----------------------------------------------------------------- POST /api/assess
def test_assess_scam_holds_and_logs_everything(client):
    res = client.post("/api/assess", json=scam_body())
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["decision"] == "hold"
    assert data["score"] >= 60
    assert data["matched_pattern"] == "prize_fee"
    assert data["is_new_recipient"] is True
    assert data["hold_seconds"] == 10
    assert data["rules_version"] == "v1"
    assert data["coaching_source"] == "template"
    assert "رسوم" in data["coaching_message"]
    assert any("\u0600" <= ch <= "\u06ff" for ch in data["coaching_message"])
    assert all(r["rule_id"] and r["text_ar"] for r in data["reasons"])

    row = log_row(client, data["tx_id"])
    assert row["risk_score"] == data["score"]
    assert row["decision"] == "hold"
    assert row["matched_pattern"] == "prize_fee"
    assert row["coaching_source"] == "template"
    assert row["rules_version"] == "v1"
    assert row["user_choice"] is None
    assert json.loads(row["reasons_json"])[0]["rule_id"]


def test_assess_normal_transfer_is_allowed_and_still_logged(client):
    body = scam_body(transaction={"amount_iqd": 90_000, "recipient_id": "r_old",
                                  "recipient_age_days": 500})
    data = client.post("/api/assess", json=body).json()
    assert data["decision"] == "allow"
    assert data["score"] == 0
    assert data["hold_seconds"] is None
    assert log_row(client, data["tx_id"])["decision"] == "allow"


def test_assess_rejects_bad_input(client):
    bad_amount = client.post("/api/assess", json=scam_body(transaction={
        "amount_iqd": 0, "recipient_id": "r1"}))
    assert bad_amount.status_code == 422

    bad_type = client.post("/api/assess", json=scam_body(transaction={
        "amount_iqd": 1000, "recipient_id": "r1", "tx_type": "atm"}))
    assert bad_type.status_code == 422

    bad_ts = client.post("/api/assess", json=scam_body(transaction={
        "amount_iqd": 1000, "recipient_id": "r1", "ts": "بعد الظهر"}))
    assert bad_ts.status_code == 422

    missing_user = client.post("/api/assess", json=scam_body(user_id="uXX"))
    assert missing_user.status_code == 404


def test_assess_accepts_flat_body_like_plan_example(client):
    """/api/assess يقبل الشكل المسطح نفسه المكتوب ب PLAN قسم 10."""
    res = client.post("/api/assess", json={
        "user_id": "u01",
        "amount_iqd": 750_000,
        "recipient_id": "r_9931",
        "recipient_age_days": 3,
        "tx_type": "transfer",
        "note": "رسوم استلام الجائزة",
        "context_message": "مبروك ربحت سحب المحفظة، حول الرسوم حتى نرسلك الجائزة",
        "ts": "2026-10-20T23:40:00+03:00",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["as_of"] == "2026-10-20T23:40:00+03:00"
    assert data["decision"] == "hold" and data["matched_pattern"] == "prize_fee"
    assert log_row(client, data["tx_id"])["risk_score"] == data["score"]


def test_assess_rejects_both_flat_and_nested_at_once(client):
    res = client.post("/api/assess", json=scam_body(amount_iqd=900_000))
    assert res.status_code == 422
    assert res.json()["detail"][0]["type"] == "extra_forbidden"


def test_assess_flat_body_without_amount_is_rejected(client):
    res = client.post("/api/assess", json={"user_id": "u01", "recipient_id": "r1"})
    assert res.status_code == 422


def test_api_never_accepts_ground_truth_fields(client):
    """ممنوع يوصل is_scam أو case_id للكشف: يرجّع 422."""
    res = client.post("/api/assess", json=scam_body(transaction={
        "amount_iqd": 750_000, "recipient_id": "r1", "is_scam": 1, "case_id": "c1"}))
    assert res.status_code == 422
    assert res.json()["detail"][0]["type"] == "extra_forbidden"


def test_two_identical_assessments_have_same_decision(client):
    body = scam_body(transaction={"amount_iqd": 400_000, "recipient_id": "r_x"})
    first = client.post("/api/assess", json=body).json()
    second = client.post("/api/assess", json=body).json()
    assert first["score"] == second["score"]
    assert first["decision"] == second["decision"]
    assert first["tx_id"] != second["tx_id"]  # كل تقييم له صف مستقل بالسجل


# ----------------------------------------------------------------- POST /api/choice
def test_choice_continue_updates_row_and_trusts_new_recipient(client):
    data = client.post("/api/assess", json=scam_body()).json()
    res = client.post("/api/choice", json={
        "tx_id": data["tx_id"], "choice": "continue", "recipient_id": "r_scam1"})
    assert res.status_code == 200
    body = res.json()
    assert body["user_choice"] == "continue" and body["trusted_added"] is True
    assert body["choice_at"]

    row = log_row(client, data["tx_id"])
    assert row["user_choice"] == "continue" and row["choice_at"] == body["choice_at"]

    conn = get_connection(client.db_path)
    try:
        trusted = conn.execute(
            "SELECT recipient_id FROM trusted_recipients WHERE user_id = 'u01'").fetchall()
    finally:
        conn.close()
    assert [t[0] for t in trusted] == ["r_scam1"]


def test_choice_cancel_does_not_trust(client):
    data = client.post("/api/assess", json=scam_body()).json()
    body = client.post("/api/choice", json={
        "tx_id": data["tx_id"], "choice": "cancel", "recipient_id": "r_scam1"}).json()
    assert body["user_choice"] == "cancel" and body["trusted_added"] is False
    conn = get_connection(client.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM trusted_recipients").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_choice_for_known_recipient_does_not_add_to_trusted(client):
    """ما نضيف للمشوقين إلا مستلم جديد (أول تحويل)."""
    body = scam_body(transaction={"amount_iqd": 100_000, "recipient_id": "r_old"})
    data = client.post("/api/assess", json=body).json()
    assert data["is_new_recipient"] is False
    res = client.post("/api/choice", json={
        "tx_id": data["tx_id"], "choice": "continue", "recipient_id": "r_old"}).json()
    assert res["trusted_added"] is False


def test_trusted_recipient_reduces_the_next_score(client):
    """تخفيف FM1: بعد continue للمستلم الجديد، التنبيه التالي يخف 25 نقطة."""
    body = scam_body(transaction={"amount_iqd": 400_000, "recipient_id": "r_new",
                                  "recipient_age_days": 500})
    first = client.post("/api/assess", json=body).json()
    assert first["score"] == 45 and first["decision"] == "warn"
    client.post("/api/choice", json={
        "tx_id": first["tx_id"], "choice": "continue", "recipient_id": "r_new"})
    second = client.post("/api/assess", json=body).json()
    assert second["score"] == 20 and second["decision"] == "allow"
    assert "r_new" in second["trusted_recipients"]


def test_choice_unknown_tx_returns_404(client):
    res = client.post("/api/choice", json={"tx_id": "live_nope", "choice": "cancel"})
    assert res.status_code == 404


def test_choice_rejects_invalid_value(client):
    data = client.post("/api/assess", json=scam_body()).json()
    res = client.post("/api/choice", json={"tx_id": data["tx_id"], "choice": "maybe"})
    assert res.status_code == 422


# ----------------------------------------------------------------- POST /api/scenario
def test_scenario_form_a_uses_existing_user(client):
    data = client.post("/api/scenario", json=scam_body()).json()
    assert data["user_id"] == "u01"
    assert data["matched_pattern"] == "prize_fee"
    assert data["decision"] == "hold"
    assert log_row(client, data["tx_id"])["user_id"] == "u01"


def test_scenario_form_b_with_custom_history(client):
    """الشكل (ب) من 14.1: تاريخ يدوي وحد ما يشوف بالمخزنة."""
    res = client.post("/api/scenario", json={
        "history": [{"ts": at(20), "amount_iqd": 25_000, "recipient_id": "r1"}],
        "balance_before_iqd": 2_000_000,
        "transaction": {
            "amount_iqd": 900_000, "recipient_id": "r_new", "note": "دفعة",
            "ts": at(0, hour=3)},
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["user_id"] is None
    assert data["as_of"] == at(0, hour=3)
    # تاريخ قصير (صف واحد) => AMOUNT_HIGH 25 + مستلم جديد 20 + وقت غريب 10 = 55 warn
    assert data["score"] == 55 and data["decision"] == "warn"
    ids = [r["rule_id"] for r in data["reasons"]]
    assert ids == ["AMOUNT_HIGH", "NEW_RECIPIENT", "ODD_HOUR"]
    assert log_row(client, data["tx_id"])["user_id"] is None


def test_scenario_form_b_needs_user_or_history(client):
    res = client.post("/api/scenario", json={
        "transaction": {"amount_iqd": 900_000, "recipient_id": "r_new"}})
    assert res.status_code == 422


def test_scenario_unknown_user_returns_404(client):
    res = client.post("/api/scenario", json=scam_body(user_id="uXX"))
    assert res.status_code == 404


# ----------------------------------------------------------------- السجل
def test_log_endpoint_returns_latest_first_with_reasons(client):
    scam = client.post("/api/assess", json=scam_body()).json()
    normal = client.post("/api/assess", json=scam_body(transaction={
        "amount_iqd": 50_000, "recipient_id": "r_old"})).json()
    data = client.get("/api/log").json()
    assert data["count"] == 2
    assert [r["tx_id"] for r in data["rows"]] == [normal["tx_id"], scam["tx_id"]]
    assert data["rows"][0]["decision"] == "allow" and data["rows"][0]["reasons"] == []
    assert data["rows"][1]["reasons"][0]["rule_id"] == "SCAM_PATTERN"
    assert data["rows"][0]["rules_version"] == "v1"


def test_log_filters_by_decision_and_user(client):
    client.post("/api/assess", json=scam_body())
    client.post("/api/assess", json=scam_body(user_id="u02"))
    assert client.get("/api/log", params={"decision": "hold"}).json()["count"] == 2
    assert client.get("/api/log", params={"decision": "allow"}).json()["count"] == 0
    assert client.get("/api/log", params={"user_id": "u02"}).json()["count"] == 1
    assert client.get("/api/log", params={"limit": 1}).json()["count"] == 1


def test_log_export_writes_jsonl_and_csv(client, tmp_path):
    data = client.post("/api/assess", json=scam_body()).json()
    client.post("/api/choice", json={"tx_id": data["tx_id"], "choice": "cancel",
                                     "recipient_id": "r_scam1"})
    res = client.get("/api/log/export")
    assert res.status_code == 200
    body = res.json()
    assert body["rows"] == 1
    assert Path(body["jsonl_path"]).exists() and Path(body["csv_path"]).exists()
    line = json.loads(Path(body["jsonl_path"]).read_text(encoding="utf-8").splitlines()[0])
    assert line["tx_id"] == data["tx_id"]
    assert line["user_choice"] == "cancel"
    assert line["coaching_message"] and any(
        "\u0600" <= ch <= "\u06ff" for ch in line["coaching_message"])
    assert "tx_id" in Path(body["csv_path"]).read_text(encoding="utf-8-sig")


# ----------------------------------------------------------------- /api/eval
def test_eval_endpoint_without_results_file(client):
    data = client.get("/api/eval").json()
    assert data["available"] is False
    assert "evaluate" in data["hint_ar"]


def test_eval_endpoint_reads_results_json(client, tmp_path):
    tmp_path.joinpath("eval_results.json").write_text(
        json.dumps({"generated_at": "2026-10-20T18:00:00", "split": "dev",
                    "rules_version": "v1", "metrics": {"any_alert": {"recall": 0.8}}}),
        encoding="utf-8")
    data = client.get("/api/eval").json()
    assert data["available"] is True
    assert data["split"] == "dev"
    assert data["results"]["metrics"]["any_alert"]["recall"] == 0.8


# ----------------------------------------------------------------- عام
def test_all_plan_endpoints_exist():
    """كل endpoints قسم 10 موجودة بالـ app."""
    paths = {r.path for r in api.app.routes if hasattr(r, "methods")}
    for path in (
        "/api/assess", "/api/choice", "/api/scenario", "/api/users",
        "/api/users/{user_id}/profile", "/api/log", "/api/log/export", "/api/eval",
        "/api/chat", "/api/training/start", "/api/training/answer",
    ):
        assert path in paths, path


def test_openapi_documents_every_endpoint():
    schema_paths = TestClient(api.app).get("/openapi.json").json()["paths"]
    assert set(schema_paths) == {
        "/api/assess", "/api/choice", "/api/scenario", "/api/users",
        "/api/users/{user_id}/profile", "/api/log", "/api/log/export", "/api/eval",
        "/api/demo_scenarios", "/api/wallet/transfer", "/api/scenario_text",
        "/api/failure_modes", "/api/chat",
        "/api/training/start", "/api/training/answer",
        "/api",
    }
    assert "post" in schema_paths["/api/assess"]
    assert "post" in schema_paths["/api/wallet/transfer"]
    assert "get" in schema_paths["/api/eval"]
    assert "get" in schema_paths["/api/failure_modes"]


def test_root_and_docs_are_available(client):
    # / الآن يخدم الواجهة (HTML)، والـ API root على /api
    assert client.get("/api").json()["docs"] == "/docs"
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/assess" in schema["paths"]


def test_api_does_not_write_to_transactions_table(client):
    """المعايشة ما تكتب بجدول المعاملات: بيانات التقييم ما تتأثر."""
    conn = get_connection(client.db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()
    client.post("/api/assess", json=scam_body())
    client.post("/api/scenario", json=scam_body())
    conn = get_connection(client.db_path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()
    assert before == after == 12


def test_coaching_message_is_never_english_only(client):
    """لو الـ LLM خرب، الرسالة تبقى عربية (قوالب) — مافي اتصال أصلاً بالاختبارات."""
    data = client.post("/api/assess", json=scam_body()).json()
    assert data["coaching_source"] == "template"
    assert sum(1 for ch in data["coaching_message"] if "\u0600" <= ch <= "\u06ff") > 20
