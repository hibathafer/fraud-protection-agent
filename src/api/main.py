"""FastAPI: endpoints (قسم 10) + السجل (قسم 9).

التشغيل:
    python -m src.db                    # مرة وحدة: ينشئ الجداول ويحمل بيانات dev
    uvicorn src.api.main:app --reload   # السيرفر
    افتحي http://127.0.0.1:8000/docs

القاعدة: الكشف والتوعية ياخذون قرارهم من القواعد. هالطبقة فقط تنسّق، تسجّل،
وتسأل المستخدم. ما تغيّر أي قرار، وما تكتب شي بجدول transactions (البيانات
الاصطناعية والتقييم ما تتأثر بالمعايشة).
"""

import csv
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from src.coaching.coach import coach
from src.config import BAGHDAD_TZ, ROOT, RULES_VERSION
from src.db import (
    add_trusted_recipient,
    all_decisions,
    get_connection,
    get_user,
    init_db,
    last_balance,
    list_users,
    log_assessment,
    read_decision_log,
    set_choice,
    trusted_recipients,
    user_history,
)
from src.detection.engine import assess
from src.detection.features import build_profile
from src.detection.rules import load_catalogue
from src.models import (
    AssessRequest,
    AssessResponse,
    ChoiceRequest,
    ChoiceResponse,
    EvalResponse,
    ExportResponse,
    LogResponse,
    LogRow,
    ProfileResponse,
    ScenarioRequest,
    UserListResponse,
)

# مكان تصدير السجل، ومكان نتيجة التقييم (يكتبها evaluate.py)
EXPORT_DIR = ROOT / "logs"
EVAL_RESULTS_PATH = ROOT / "docs" / "eval_results.json"

# وقت الانتظار قبل ما يسمح بإكمال عملية بحالة hold (قسم 11)
HOLD_WAIT_SECONDS = 10

_CATALOGUE = None


def catalogue():
    """كتالوج الأنماط: نقراه مرة وحدة بالعملية."""
    global _CATALOGUE
    if _CATALOGUE is None:
        _CATALOGUE = load_catalogue()
    return _CATALOGUE


def now_iso() -> str:
    return datetime.now(BAGHDAD_TZ).isoformat(timespec="seconds")


def get_db():
    """اتصال جديد لكل طلب، ونغلقه بعدين."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def lifespan(app: FastAPI):
    """عند التشغيل: ينشئ الجداول إذا ناقصة ويجهّز مجلد التصدير."""
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Fraud & Scam Protection Agent",
    description="طبقة كشف بالقواعد + توعية باللهجة. القرار من القواعد فقط.",
    version=RULES_VERSION,
    lifespan=lifespan,
)

# تصدير السجل قابل للتحميل من المتصفح (9)
app.mount("/logs", StaticFiles(directory=str(EXPORT_DIR), check_dir=False), name="logs")


@app.get("/")
def root():
    return {
        "name_ar": "وكيل حماية من الاحتيال",
        "docs": "/docs",
        "endpoints": [
            "POST /api/assess", "POST /api/choice", "POST /api/scenario",
            "GET /api/users", "GET /api/users/{user_id}/profile",
            "GET /api/log", "GET /api/log/export", "GET /api/eval",
        ],
        "rules_version": RULES_VERSION,
    }


# ----------------------------------------------------------------- أدوات داخلية
def _resolve_ts(history, requested) -> str:
    """وقت التقييم: المدخل أولوية، وبعده آخر وقت بالمخزنة، وبعده الحين.

    مهم للعرض: بياناتنا اصطناعية لآخر 2026-10-20، فلو استعملنا وقت الحين
    أحياناً ما نلاقي تاريخ (وهالمستخدم يطلع عنده مستلم جديد دائماً).
    """
    if requested:
        return requested
    if history:
        return max(str(row["ts"]) for row in history)
    return now_iso()


def _new_tx_id() -> str:
    return "live_" + uuid.uuid4().hex[:10]


def _was_new_recipient(reasons) -> bool:
    return any(r.get("rule_id") == "NEW_RECIPIENT" and r.get("points", 0) > 0
               for r in reasons)


def _row_to_response(tx, user_id, result, coaching, log_id, as_of, trusted) -> dict:
    pattern = result.get("pattern") or {}
    return {
        "tx_id": tx.get("tx_id"),
        "log_id": log_id,
        "user_id": user_id,
        "as_of": as_of,
        "score": result["score"],
        "raw_score": result["raw_score"],
        "decision": result["decision"],
        "reasons": result["reasons"],
        "matched_pattern": result.get("matched_pattern"),
        "pattern_name_ar": pattern.get("name_ar"),
        "coaching_message": coaching["message"],
        "coaching_source": coaching["source"],
        "is_new_recipient": any(
            r["rule_id"] == "NEW_RECIPIENT" and r["points"] > 0 for r in result["reasons"]
        ),
        "trusted_recipients": trusted,
        "hold_seconds": HOLD_WAIT_SECONDS if result["decision"] == "hold" else None,
        "rules_version": result["rules_version"],
    }


def _assess_and_log(conn, user_id, history, trusted, tx_in, use_llm=False) -> dict:
    """المسار المشترك: profile ثم كشف ثم توعية ثم تسجيل صف بالسجل."""
    as_of = _resolve_ts(history, tx_in.ts)
    balance = tx_in.balance_before_iqd
    if balance is None and user_id:
        balance = last_balance(conn, user_id)
    tx = tx_in.to_tx(as_of, balance)
    tx["tx_id"] = tx.get("tx_id") or _new_tx_id()

    profile = build_profile(history, as_of, tx_in.recipient_id, trusted)
    result = assess(tx, profile, catalogue())
    coaching = coach(result, use_llm=use_llm)
    log_id = log_assessment(conn, tx["tx_id"], user_id, result, coaching)
    return _row_to_response(tx, user_id, result, coaching, log_id, as_of, trusted)


# ----------------------------------------------------------------- (10) نقاط التقييم
@app.post("/api/assess", response_model=AssessResponse)
def api_assess(payload: AssessRequest, conn=Depends(get_db)):
    """يقيم معاملة لمستخدم موجود ويسجلها بالسجل."""
    user = get_user(conn, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"ماكو مستخدم بالمعرف {payload.user_id}")
    history = user_history(conn, payload.user_id)
    trusted = trusted_recipients(conn, payload.user_id)
    return _assess_and_log(conn, payload.user_id, history, trusted, payload.transaction,
                           payload.use_llm)


@app.post("/api/scenario", response_model=AssessResponse)
def api_scenario(payload: ScenarioRequest, conn=Depends(get_db)):
    """ديمو الحكم (14.1): شكل (أ) مستخدم موجود، أو شكل (ب) تاريخ يدوي."""
    if payload.user_id:
        user = get_user(conn, payload.user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"ماكو مستخدم بالمعرف {payload.user_id}")
        history = user_history(conn, payload.user_id) + [h.to_row() for h in payload.history]
        trusted = trusted_recipients(conn, payload.user_id)
    else:
        history = [h.to_row() for h in payload.history]
        trusted = []
    tx_in = payload.transaction
    if tx_in.balance_before_iqd is None and payload.balance_before_iqd is not None:
        tx_in = tx_in.model_copy(update={"balance_before_iqd": payload.balance_before_iqd})
    return _assess_and_log(conn, payload.user_id, history, trusted, tx_in, payload.use_llm)


@app.post("/api/choice", response_model=ChoiceResponse)
def api_choice(payload: ChoiceRequest, conn=Depends(get_db)):
    """قرار المستخدم: يحدّث نفس صف السجل.

    إذا choice=continue والمعاملة كانت لمستلم جديد، نضيفه لقائمة الموثوقين
    حتى ما يتكرر الإنذار (تخفيف FM1 وFM3 من PLAN قسم 13).
    """
    row = set_choice(conn, payload.tx_id, payload.choice)
    if not row:
        raise HTTPException(status_code=404, detail=f"ماكو تقييم بالمعرف {payload.tx_id}")

    reasons = json.loads(row.get("reasons_json") or "[]")
    trusted_added = False
    if payload.choice == "continue" and payload.recipient_id and row.get("user_id"):
        if _was_new_recipient(reasons):
            trusted_added = add_trusted_recipient(
                conn, row["user_id"], payload.recipient_id, added_at=row.get("choice_at")
            )
    message = (
        "سُجّل اختيارك. هذا المستلم دخل قائمة الموثوقين، فما راح ينبّهك عليه."
        if trusted_added else
        "سُجّل اختيارك."
    )
    return {
        "tx_id": row["tx_id"],
        "log_id": row["log_id"],
        "user_id": row["user_id"],
        "user_choice": payload.choice,
        "choice_at": row["choice_at"],
        "trusted_added": trusted_added,
        "message_ar": message,
    }


# ----------------------------------------------------------------- المستخدمون
@app.get("/api/users", response_model=UserListResponse)
def api_users(conn=Depends(get_db)):
    """قائمة مستخدمي dev (ما نكشف مستخدمي test المعزولين)."""
    users = list_users(conn, split="dev")
    return {"count": len(users), "users": users}


@app.get("/api/users/{user_id}/profile", response_model=ProfileResponse)
def api_user_profile(user_id: str, conn=Depends(get_db)):
    """إحصاءات المستخدم (7.1) لعرضها بالواجهة."""
    user = get_user(conn, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"ماكو مستخدم بالمعرف {user_id}")
    history = user_history(conn, user_id)
    as_of = _resolve_ts(history, None)
    trusted = trusted_recipients(conn, user_id)
    profile = build_profile(history, as_of, None, trusted)
    return {
        "user_id": user_id,
        "name": user.get("name"),
        "archetype": user.get("archetype"),
        "as_of": as_of,
        "profile": profile,
    }


# ----------------------------------------------------------------- السجل (9)
def _log_row(row: dict) -> dict:
    try:
        reasons = json.loads(row.get("reasons_json") or "[]")
    except json.JSONDecodeError:
        reasons = []
    return {
        "log_id": row["log_id"],
        "tx_id": row.get("tx_id"),
        "user_id": row.get("user_id"),
        "created_at": row.get("created_at"),
        "risk_score": row.get("risk_score"),
        "decision": row.get("decision"),
        "reasons": reasons,
        "matched_pattern": row.get("matched_pattern"),
        "coaching_message": row.get("coaching_message"),
        "coaching_source": row.get("coaching_source"),
        "user_choice": row.get("user_choice"),
        "choice_at": row.get("choice_at"),
        "rules_version": row.get("rules_version"),
    }


@app.get("/api/log", response_model=LogResponse)
def api_log(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    decision: Literal["allow", "warn", "hold"] | None = None,
    user_id: str | None = None,
    conn=Depends(get_db),
):
    """سجل القرارات، الأحدث أول. count = عدد الصفوف المرجعة."""
    rows = read_decision_log(conn, limit=limit, offset=offset, decision=decision, user_id=user_id)
    return {"count": len(rows), "rows": [_log_row(r) for r in rows]}


EXPORT_COLUMNS = (
    "log_id", "tx_id", "user_id", "created_at", "risk_score", "decision",
    "matched_pattern", "coaching_source", "coaching_message", "user_choice",
    "choice_at", "rules_version",
)


@app.get("/api/log/export", response_model=ExportResponse)
def api_log_export(conn=Depends(get_db)):
    """يكتب السجل بملف JSONL وملف CSV بنفسه (9)."""
    rows = all_decisions(conn)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = EXPORT_DIR / "decision_log.jsonl"
    csv_path = EXPORT_DIR / "decision_log.csv"

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_log_row(row), ensure_ascii=False) + "\n")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["coaching_message"] = " ".join(str(row.get("coaching_message") or "").split())
            writer.writerow(flat)

    return {
        "rows": len(rows),
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path),
        "jsonl_url": "/logs/decision_log.jsonl",
        "csv_url": "/logs/decision_log.csv",
    }


@app.get("/api/eval", response_model=EvalResponse)
def api_eval():
    """آخر نتائج التقييم من ملف JSON اللي يكتبه evaluate.py (10)."""
    if not EVAL_RESULTS_PATH.exists():
        return {
            "available": False,
            "hint_ar": "ماكو نتائج بعد. شغلي: python -m src.eval.evaluate",
            "results": None,
        }
    with open(EVAL_RESULTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "available": True,
        "generated_at": data.get("generated_at"),
        "split": data.get("split"),
        "rules_version": data.get("rules_version"),
        "hint_ar": "النتائج محفوظة من آخر تشغيل.",
        "results": data,
    }
