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
from src.agents import dialogue, intake, training
from src.db import (
    add_trusted_recipient,
    all_decisions,
    count_user_chat_messages,
    get_connection,
    get_log_row,
    get_user,
    init_db,
    last_balance,
    list_users,
    log_assessment,
    log_chat_turn,
    read_decision_log,
    set_choice,
    set_final_status,
    trusted_recipients,
    user_history,
)
from src.detection.engine import assess
from src.detection.features import build_profile
from src.detection.rules import load_catalogue
from src.integrations import wallet_flow, zain_cash
from src.models import (
    AssessRequest,
    AssessResponse,
    ChatRequest,
    ChatResponse,
    ChoiceRequest,
    ChoiceResponse,
    EvalResponse,
    ExportResponse,
    LogResponse,
    LogRow,
    ProfileResponse,
    ScenarioRequest,
    ScenarioTextRequest,
    ScenarioTextResponse,
    TrainingAnswerRequest,
    TrainingStartRequest,
    TrainingResponse,
    TransactionIn,
    UserListResponse,
    WalletTransferRequest,
    WalletTransferResponse,
)

# مكان تصدير السجل، ومكان نتيجة التقييم (يكتبها evaluate.py)
EXPORT_DIR = ROOT / "logs"
EVAL_RESULTS_PATH = ROOT / "docs" / "eval_results.json"
# نتيجة سكربت حالات الفشل (T7) — تقراها صفحة النتائج
FAILURE_MODES_PATH = ROOT / "docs" / "failure_modes_run.json"

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
    """عند التشغيل: ينشئ الجداول، ويرمّل بيانات dev إذا القاعدة فاضية.

    مهم للنشر على سيرفر: الحاوية تبدأ بدون ملف fraud.db، فنحمّل البيانات
    الاصطناعية (dev فقط) تلقائياً حتى الديمو يشتغل من أول لحظة.
    """
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()
    if n_users == 0:
        from src.db import load_csvs
        load_csvs(split="dev")  # dev فقط — data/test_sealed/ ما تنلمس هنا أبداً
    yield


app = FastAPI(
    title="Fraud & Scam Protection Agent",
    description="طبقة كشف بالقواعد + توعية باللهجة. القرار من القواعد فقط.",
    version=RULES_VERSION,
    lifespan=lifespan,
)

# تصدير السجل قابل للتحميل من المتصفح (9)
app.mount("/logs", StaticFiles(directory=str(EXPORT_DIR), check_dir=False), name="logs")


@app.get("/api")
def root():
    return {
        "name_ar": "وكيل حماية من الاحتيال",
        "docs": "/docs",
        "endpoints": [
            "POST /api/assess", "POST /api/choice", "POST /api/scenario",
            "POST /api/scenario_text", "POST /api/wallet/transfer",
            "GET /api/users", "GET /api/users/{user_id}/profile",
            "GET /api/log", "GET /api/log/export", "GET /api/eval",
            "GET /api/failure_modes",
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


# ----------------------------------------------------------------- نص حر (T6: Intake)
@app.post("/api/scenario_text", response_model=ScenarioTextResponse)
def api_scenario_text(payload: ScenarioTextRequest, conn=Depends(get_db)):
    """Intake Agent: نص حر أو JSON ← استخراج منظّم ← كشف ← توعية (T6).

    - ناقص المبلغ أو المستلم: سؤال واحد قصير بالعربي (status=needs_clarification)
      بدون أي تخمين — الواجهة تعرض السؤال وتكمّل بالإجابة.
    - LLM مطفي/فشل أو JSON مكسور: رسالة عربية واضحة (status=cannot_parse).
    - بدون user_id: ملف مؤقت بدون تاريخ → مسار n_tx < 10 (عتبات ثابتة).
    النص بيانات غير موثوقة: ينقرأ كبيانات فقط، والقرار من القواعد.
    """
    result = intake.parse_intake(payload.text)
    if result["status"] != "ok":
        return {
            "status": result["status"],
            "message_ar": result.get("question_ar") or result.get("message_ar") or "",
            "extracted": result.get("extracted") or {},
            "intake_source": result.get("source"),
            "assessment": None,
        }

    ex = result["extracted"]
    user_id = payload.user_id or ex.get("user_id")
    if user_id:
        if not get_user(conn, user_id):
            raise HTTPException(status_code=404, detail=f"ماكو مستخدم بالمعرف {user_id}")
        history = user_history(conn, user_id)
        trusted = trusted_recipients(conn, user_id)
    else:
        # ملف مؤقت بدون تاريخ: الإحصاءات فاضية والقواعد تستعمل العتبات الثابتة
        history, trusted = [], []

    tx_in = TransactionIn(
        amount_iqd=ex["amount_iqd"],
        recipient_id=ex["recipient_id"],
        recipient_age_days=ex.get("recipient_age_days"),
        tx_type=ex.get("tx_type") or "transfer",
        note=ex.get("note"),
        context_message=ex.get("context_message"),
        tx_id=_new_tx_id(),
    )
    assessment = _assess_and_log(conn, user_id, history, trusted, tx_in, payload.use_llm)
    return {
        "status": "assessed",
        "message_ar": "",
        "extracted": ex,
        "intake_source": result.get("source"),
        "assessment": assessment,
    }


# ----------------------------------------------------------------- حوار (T11)
@app.post("/api/chat", response_model=ChatResponse)
def api_chat(payload: ChatRequest, conn=Depends(get_db)):
    """Dialogue Agent (T11): جواب عن سؤال المستخدم — هذه المعاملة فقط.

    - يقرأ حقائق القرار من السجل (أسباب + نمط + نصيحة) ويرد بـ ≤ 50 كلمة:
      رد جاهز دائماً، والـ LLM اختياري فوقه (use_llm=True + COACH_MODE).
    - **لا يغيّر القرار أبداً**: لا يكتب بـ decision_log ولا يمسّ نتيجة التقييم —
      الكتابة الوحيدة بجدول chat_turns.
    - حد 5 رسائل مستخدم لكل معاملة، بعدها رد وداع جاهز بدون تسجيل.
    - الرسالة بيانات غير موثوقة: تنعزل بـ <user_message> وما تنفَّذ كتعليمات.
    """
    row = get_log_row(conn, payload.tx_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"ماكو معاملة بالمعرف {payload.tx_id}")

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="الرسالة فارغة")

    used = count_user_chat_messages(conn, payload.tx_id)
    if used >= dialogue.MAX_USER_MESSAGES:
        # انوصل للحد: ردّ جاهز بدون تسجيل (الجدول يبقى بخمس رسائل مستخدم)
        return {
            "tx_id": payload.tx_id,
            "turn": used,
            "reply_ar": dialogue.LIMIT_REPLY,
            "source": "limit",
            "turns_used": used,
            "limit_reached": True,
        }

    result = dialogue.reply(
        row, message, catalogue(), use_llm=payload.use_llm
    )
    turn = used + 1
    log_chat_turn(conn, payload.tx_id, turn, "user", message, "user")
    log_chat_turn(conn, payload.tx_id, turn, "assistant", result["text"], result["source"])
    return {
        "tx_id": payload.tx_id,
        "turn": turn,
        "reply_ar": result["text"],
        "source": result["source"],
        "turns_used": turn,
        "limit_reached": False,
    }


# ----------------------------------------------------------------- تدريب (T12)
def _training_view(scenario_id, scenario, status, turn,
                   line="", line_source="script", evaluation=None) -> dict:
    """منظر موحد لكل ردود التدريب — معلن "تدريب" بكل حالة."""
    return {
        "scenario_id": scenario_id,
        "title_ar": scenario["title_ar"],
        "training_notice_ar": training.TRAINING_NOTICE,
        "status": status,
        "turn": turn,
        "total_turns": len(scenario["turns"]),
        "line_ar": line,
        "line_source": line_source,
        "evaluation": evaluation,
    }


@app.post("/api/training/start", response_model=TrainingResponse)
def api_training_start(payload: TrainingStartRequest):
    """وضع التدريب (T12): يبدأ سيناريو تعليمي — بلا اتصال بقاعدة البيانات.

    - معلن "تدريب" بكل رد، وما يقرأ أي بيانات مستخدم ولا يكتب بالسجل
      (مو عمداً `Depends(get_db)`: صفر لمسة للقاعدة).
    - سيناريوهات مكتوبة داخل `src/agents/training.py` (اصطناعية 100%).
    - `use_llm=True`: الـ LLM يلعب صوت السطر — والفشل يرجع السطر الأصلي.
    """
    scenario_id = payload.scenario_id or training.DEFAULT_SCENARIO
    scenario = training.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"سيناريو غير معروف: {scenario_id}")
    line, source = training.dramatize(
        scenario, scenario["turns"][0]["line_ar"], use_llm=payload.use_llm
    )
    return _training_view(scenario_id, scenario, "playing", 1, line, source)


@app.post("/api/training/answer", response_model=TrainingResponse)
def api_training_answer(payload: TrainingAnswerRequest):
    """إجابة المستخدم عن سيناريو تدريبي (T12) — بلا نص حر وبلا حالة بالخادم.

    - الإجابات enums فقط: flag (هذا احتيال) / continue (أكمل) — ما توصل للـ LLM.
    - الإجابات تُرسَل تراكمياً: أقل من عدد الخطوات = السطر التالي،
      مساوية له = التقييم النهائي (بايثون صراحة: صح/غلط من حكم السيناريو).
    - لا يمس الكشف ولا البيانات: صفر اتصال بقاعدة البيانات.
    """
    scenario_id = payload.scenario_id
    scenario = training.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"سيناريو غير معروف: {scenario_id}")

    total = len(scenario["turns"])
    answered = len(payload.answers)
    if answered > total:
        raise HTTPException(
            status_code=422,
            detail=f"عدد الإجابات ({answered}) أكبر من خطوات السيناريو ({total})",
        )

    if answered == total:
        try:
            evaluation = training.evaluate(scenario, payload.answers)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _training_view(scenario_id, scenario, "finished", total,
                              evaluation=evaluation)

    line, source = training.dramatize(
        scenario, scenario["turns"][answered]["line_ar"], use_llm=payload.use_llm
    )
    return _training_view(scenario_id, scenario, "playing", answered + 1,
                          line, source)


# ----------------------------------------------------------------- محفظة Zain Cash
@app.post("/api/wallet/transfer", response_model=WalletTransferResponse)
def api_wallet_transfer(payload: WalletTransferRequest, conn=Depends(get_db)):
    """اعتراض طلب التحويل من المحفظة قبل تنفيذها (الترتيب المطلوب):

    1. كشف بالقواعد (engine) + توعية (coach) — القرار من القواعد فقط.
    2. allow    → ننفذ التحويل عبر محفظة Zain Cash الوهمية ونرجّع إيصال.
    3. warn/hold → نعلّق التحويل (فترة تهدئة 10 ثواني) وننتظر POST /api/choice.

    pin ما يوصل للكشف ولا للسجل ولا للـ LLM: يبقى بذاكرة العملية فقط.
    """
    user_id = payload.user_id
    if user_id:
        if not get_user(conn, user_id):
            raise HTTPException(status_code=404, detail=f"ماكو مستخدم بالمعرف {user_id}")
        history = user_history(conn, user_id)
        trusted = trusted_recipients(conn, user_id)
    else:
        # مستخدم غير مربوط: ملف مؤقت بدون تاريخ (نفس منطق السيناريو الشكل ب)
        history, trusted = [], []

    tx_in = TransactionIn(
        amount_iqd=payload.amount_iqd,
        recipient_id=payload.recipient_msisdn,
        recipient_age_days=payload.recipient_age_days,
        tx_type="transfer",
        balance_before_iqd=None,
        note=payload.note,
        context_message=payload.context_message,
        ts=payload.ts,
        tx_id="zc_" + uuid.uuid4().hex[:10],
    )
    # المسار المشترك نفسه: profile → كشف → توعية → تسجيل بالسجل
    data = _assess_and_log(conn, user_id, history, trusted, tx_in, payload.use_llm)

    transfer_request = {
        "sender_msisdn": payload.sender_msisdn,
        "recipient_msisdn": payload.recipient_msisdn,
        "amount_iqd": payload.amount_iqd,
        "pin": payload.pin,
    }
    try:
        routed = wallet_flow.route(data["decision"], transfer_request, data["tx_id"])
    except zain_cash.ZainCashError as exc:  # دفاع: المدخلات مفحوصة من Pydantic قبل كذا
        raise HTTPException(status_code=422, detail=str(exc))

    if routed["action"] == "execute":
        receipt = routed["receipt"]
        set_final_status(conn, data["tx_id"], "completed", receipt)
        return {
            **data,
            "status": "executed",
            "receipt": receipt,
            "cooling_off_seconds": None,
            "final_status": "completed",
        }

    set_final_status(conn, data["tx_id"], "pending")
    return {
        **data,
        "status": "blocked",
        "receipt": None,
        "cooling_off_seconds": routed["cooling_off_seconds"],
        "final_status": "pending",
    }


@app.post("/api/choice", response_model=ChoiceResponse)
def api_choice(payload: ChoiceRequest, conn=Depends(get_db)):
    """قرار المستخدم: يحدّث نفس صف السجل.

    إذا choice=continue والمعاملة كانت لمستلم جديد، نضيفه لقائمة الموثوقين
    حتى ما يتكرر الإنذار (تخفيف FM1 وFM3 من PLAN قسم 13).

    وإذا كان التقييم جاي من محفظة Zain Cash معلّقاً (warn/hold): continue
    ينفّذ التحويل ويرجع الإيصال، وcancel يُلغيه — كل شي يتسجّل بـ final_status.
    """
    row = set_choice(conn, payload.tx_id, payload.choice)
    if not row:
        raise HTTPException(status_code=404, detail=f"ماكو تقييم بالمعرف {payload.tx_id}")

    # تحويل المحفظة المعلّق: نفّذ أو ألغِ (الـ PIN بالذاكرة فقط، ما انكتب بأي مكان)
    receipt = None
    pending = wallet_flow.take_pending(payload.tx_id)
    if pending and payload.choice == "continue":
        try:
            receipt = wallet_flow.execute(pending)
        except zain_cash.ZainCashError as exc:
            wallet_flow.hold_pending(payload.tx_id, pending)  # نعيده حتى ما يضيع
            raise HTTPException(status_code=422, detail=str(exc))

    final_status = "completed" if payload.choice == "continue" else "cancelled"
    set_final_status(conn, payload.tx_id, final_status, receipt)

    reasons = json.loads(row.get("reasons_json") or "[]")
    trusted_added = False
    if payload.choice == "continue" and payload.recipient_id and row.get("user_id"):
        if _was_new_recipient(reasons):
            trusted_added = add_trusted_recipient(
                conn, row["user_id"], payload.recipient_id, added_at=row.get("choice_at")
            )
    if receipt:
        message = f"تم تنفيذ التحويل. رقم الإيصال: {receipt['receipt_id']}"
    elif trusted_added:
        message = "سُجّل اختيارك. هذا المستلم دخل قائمة الموثوقين، فما راح ينبّهك عليه."
    else:
        message = "سُجّل اختيارك."
    return {
        "tx_id": row["tx_id"],
        "log_id": row["log_id"],
        "user_id": row["user_id"],
        "user_choice": payload.choice,
        "choice_at": row["choice_at"],
        "trusted_added": trusted_added,
        "message_ar": message,
        "final_status": final_status,
        "receipt": receipt,
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
        "final_status": row.get("final_status"),
        "receipt": _parse_receipt(row.get("receipt_json")),
    }


def _parse_receipt(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


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
    "choice_at", "rules_version", "final_status", "receipt_json",
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


# ----------------------------------------------------------------- حالات الفشل (T7)
@app.get("/api/failure_modes")
def api_failure_modes():
    """آخر نتيجة سكربت حالات الفشل (T7) — تُعرض بصفحة النتائج كما هي."""
    if not FAILURE_MODES_PATH.exists():
        return {
            "available": False,
            "hint_ar": "ماكو نتائج بعد. شغلي: python -m src.eval.failure_modes",
            "cases": [],
        }
    with open(FAILURE_MODES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {"available": True, "hint_ar": "", **data}


# ----------------------------------------------------------------- السيناريوهات الجاهزة
@app.get("/api/demo_scenarios")
def api_demo_scenarios():
    """قائمة السيناريوهات الجاهزة من ملفات demo/."""
    demo_dir = ROOT / "demo"
    if not demo_dir.exists():
        return {"count": 0, "scenarios": []}
    scenarios = []
    for f in sorted(demo_dir.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        scenarios.append({
            "id": f.stem,
            "name_ar": data.get("name_ar", f.stem),
            "description_ar": data.get("description_ar", ""),
            "payload": data.get("payload", data),
        })
    return {"count": len(scenarios), "scenarios": scenarios}


# ----------------------------------------------------------------- خدمة الواجهة
# صفحات الويب تُخدم من مجلد web/ (بعد كل الـ routes حتى ما تتداخل)
app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="web")
