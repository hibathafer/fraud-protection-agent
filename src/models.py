"""مخططات Pydantic للـ API (قسم 4 و10).

كل مدخل يمرّ من هنا قبل ما يوصل للكشف. extra="forbid" يعني إن أي حقل زيادة
(مثل is_scam أو case_id) يرجّع 422 بدل ما يوصل للكشف ساكتاً.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TxType = Literal["transfer", "bill", "merchant", "cashout"]
Choice = Literal["continue", "cancel", "no_response"]
Decision = Literal["allow", "warn", "hold"]

MAX_AMOUNT = 10_000_000_000
MAX_NOTE = 300
MAX_MESSAGE = 1000
MAX_ID = 64


def _check_ts(value: str | None) -> str | None:
    """يتأكد إن الوقت ISO بصيغة يفهمها datetime.fromisoformat."""
    if value in (None, ""):
        return None
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+03:00"))
    except ValueError as exc:
        raise ValueError("الوقت لازم يكون ISO، مثل 2026-10-20T23:40:00+03:00") from exc
    return str(value).strip()


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ المعاملة
class TransactionIn(ApiModel):
    """معاملة واردة. balance_before_iqd و ts اختيارية: نكملها من سجل المستخدم."""

    amount_iqd: int = Field(gt=0, le=MAX_AMOUNT, description="المبلغ بالدينار")
    recipient_id: str = Field(min_length=1, max_length=MAX_ID)
    recipient_age_days: int | None = Field(default=None, ge=0, le=3650)
    tx_type: TxType = Field(default="transfer", description="transfer / bill / merchant / cashout")
    balance_before_iqd: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=MAX_NOTE)
    context_message: str | None = Field(default=None, max_length=MAX_MESSAGE)
    ts: str | None = Field(default=None, description="وقت المعاملة، الافتراضي آخر وقت بالمخزنة")
    tx_id: str | None = Field(default=None, max_length=MAX_ID, description="اختياري، نولّد واحد لو ما انمرّر")

    _ts = field_validator("ts")(_check_ts)

    def to_tx(self, ts: str, balance_before: int | None = None) -> dict:
        """يرجع dict بالمفاتيح نفسها اللي يتوقعها المحرك (7.3)."""
        return {
            "ts": ts,
            "amount_iqd": int(self.amount_iqd),
            "balance_before_iqd": int(balance_before or 0),
            "tx_type": self.tx_type,
            "recipient_id": self.recipient_id,
            "recipient_age_days": self.recipient_age_days,
            "note": self.note or None,
            "context_message": self.context_message or None,
            "tx_id": self.tx_id,
        }


# ------------------------------------------------------------------ /api/assess
# حقول المعاملة المسطحة: مثال PLAN قسم 10 يرسلها مسطحة beside user_id
FLAT_TX_FIELDS = (
    "amount_iqd", "recipient_id", "recipient_age_days", "tx_type",
    "balance_before_iqd", "note", "context_message", "ts", "tx_id",
)


class AssessRequest(ApiModel):
    """مدخل /api/assess: مستخدم موجود + معاملة.

    يقبل الشكلين: مسطّح (مثل مثال PLAN قسم 10) أو {"transaction": {...}}.
    إذا انرسل الشكلين بنفس الوقت يرجّع 422 (حقل زايد).
    """

    user_id: str = Field(min_length=1, max_length=MAX_ID)
    transaction: TransactionIn
    use_llm: bool = Field(default=False, description="صياغة رسالة بالـ LLM (مطفي افتراضياً)")

    @model_validator(mode="before")
    @classmethod
    def accept_flat_or_nested(cls, data):
        if not isinstance(data, dict) or "transaction" in data:
            return data
        flat = {k: v for k, v in ((k, data.get(k)) for k in FLAT_TX_FIELDS) if v is not None}
        if not flat:
            return data
        data = dict(data)
        for key in FLAT_TX_FIELDS:
            data.pop(key, None)
        data["transaction"] = flat
        return data

    @property
    def tx(self) -> TransactionIn:
        return self.transaction


# ------------------------------------------------------------------ /api/scenario
class HistoryItem(ApiModel):
    """سطر تاريخ يدوي لسيناريو الحكم (شكل ب من قسم 14.1)."""

    ts: str
    amount_iqd: int = Field(gt=0, le=MAX_AMOUNT)
    recipient_id: str | None = Field(default=None, max_length=MAX_ID)
    tx_type: TxType = Field(default="transfer")

    _ts = field_validator("ts")(_check_ts)

    def to_row(self) -> dict:
        return {
            "ts": self.ts,
            "amount_iqd": int(self.amount_iqd),
            "recipient_id": self.recipient_id,
            "tx_type": self.tx_type,
        }


class ScenarioRequest(ApiModel):
    """سيناريو الحكم: شكل (أ) مستخدم موجود، أو شكل (ب) تاريخ يدوي (14.1)."""

    user_id: str | None = Field(default=None, max_length=MAX_ID)
    history: list[HistoryItem] = Field(default_factory=list, max_length=500)
    balance_before_iqd: int | None = Field(default=None, ge=0)
    transaction: TransactionIn
    use_llm: bool = Field(default=False, description="صياغة رسالة بالـ LLM (مطفي افتراضياً)")

    @model_validator(mode="after")
    def need_context(self):
        if not self.user_id and not self.history:
            raise ValueError("إما user_id أو history: بدونهم ما نعرف عادات المستخدم")
        return self


# ------------------------------------------------------------------ /api/choice
class ChoiceRequest(ApiModel):
    """قرار المستخدم. recipient_id اختياري، وإذا ما انمرّر نضيفه من الـ tx_id."""

    tx_id: str = Field(min_length=1, max_length=MAX_ID)
    choice: Choice
    recipient_id: str | None = Field(default=None, max_length=MAX_ID)


# ------------------------------------------------------------------ /api/wallet/transfer
MSISDN_PATTERN = r"^07\d{9}$"
PIN_PATTERN = r"^\d{4,6}$"


class WalletTransferRequest(ApiModel):
    """طلب تحويل من محفظة Zain Cash (محاكاة) — يمر على الكشف قبل التنفيذ.

    pin: الرمز السري يوصل للمحفظة الوهمية فقط. ما ينحفظ بالسجل، وما يمر
    للكشف ولا للـ LLM.
    """

    sender_msisdn: str = Field(pattern=MSISDN_PATTERN, description="رقم المرسل: 11 رقم يبدأ بـ 07")
    recipient_msisdn: str = Field(pattern=MSISDN_PATTERN, description="رقم المستلم: 11 رقم يبدأ بـ 07")
    amount_iqd: int = Field(gt=0, le=MAX_AMOUNT, description="المبلغ بالدينار")
    pin: str = Field(pattern=PIN_PATTERN, description="4-6 أرقام — لا يُسجَّل ولا يُرسل للكشف")
    user_id: str | None = Field(
        default=None, max_length=MAX_ID,
        description="اختياري: ربط بمستخدم موجود حتى يستعمل تاريخ عاداته",
    )
    recipient_age_days: int | None = Field(default=None, ge=0, le=3650)
    note: str | None = Field(default=None, max_length=MAX_NOTE)
    context_message: str | None = Field(default=None, max_length=MAX_MESSAGE)
    ts: str | None = Field(default=None, description="وقت التحويل، الافتراضي الحين")
    use_llm: bool = Field(default=False, description="صياغة رسالة بالـ LLM (مطفي افتراضياً)")

    _ts = field_validator("ts")(_check_ts)

    @model_validator(mode="after")
    def different_parties(self):
        if self.sender_msisdn == self.recipient_msisdn:
            raise ValueError("رقم المستلم لازم يختلف عن رقم المرسل")
        return self


# ------------------------------------------------------------------ /api/scenario_text (T6)
class IntakeExtract(ApiModel):
    """الـ JSON الناتج من Intake Agent — حقول T6 + سؤال توضيحي اختياري.

    كل الحقول مسموح تجي null (ينقصها يتسأل المستخدم بسؤال بعدين).
    """

    user_id: str | None = Field(default=None, max_length=MAX_ID)
    amount_iqd: int | None = Field(default=None, gt=0, le=MAX_AMOUNT)
    recipient_id: str | None = Field(default=None, max_length=MAX_ID)
    recipient_age_days: int | None = Field(default=None, ge=0, le=3650)
    tx_type: TxType = Field(default="transfer")
    note: str | None = Field(default=None, max_length=MAX_NOTE)
    context_message: str | None = Field(default=None, max_length=MAX_MESSAGE)
    needs_clarification: str | None = Field(default=None, max_length=300)


class ScenarioTextRequest(ApiModel):
    """نص حر (عربي/لهجة/إنجليزي) أو JSON جاهز — حد 2000 حرف (T6)."""

    text: str = Field(max_length=2000, description="النص الحر أو JSON")
    user_id: str | None = Field(
        default=None, max_length=MAX_ID,
        description="اختياري: ربط بمستخدم موجود لاستعادة تاريخ عاداته",
    )
    use_llm: bool = Field(default=False, description="صياغة رسالة التوعية بالـ LLM")


class ChatRequest(ApiModel):
    """سؤال المستخدم عن معاملة وحدة (T11 — الحوار)."""

    tx_id: str = Field(max_length=MAX_ID, description="معرف المعاملة من آخر نافذة")
    message: str = Field(
        min_length=1, max_length=500,
        description="سؤال المستخدم — بيانات غير موثوقة، ما تنفَّذ كتعليمات",
    )
    use_llm: bool = Field(default=False, description="صياغة الرد بالـ LLM (مطفي افتراضياً)")


# ------------------------------------------------------------------ مخرجات
class ReasonOut(BaseModel):
    rule_id: str
    points: int
    text_ar: str


class AssessResponse(BaseModel):
    """نتيجة الكشف + رسالة التوعية + رقم السجل (10)."""

    tx_id: str
    log_id: int | None = None
    user_id: str | None = None
    as_of: str = Field(description="وقت المعاملة المستعمل وقت التقييم")
    score: int
    raw_score: int
    decision: Decision
    reasons: list[ReasonOut]
    matched_pattern: str | None = None
    pattern_name_ar: str | None = None
    coaching_message: str
    coaching_source: str = Field(description="template أو llm")
    is_new_recipient: bool
    trusted_recipients: list[str] = Field(default_factory=list)
    hold_seconds: int | None = Field(default=None, description="بالـ hold: كم ثانية ينتظر المستخدم")
    rules_version: str


class ChoiceResponse(BaseModel):
    tx_id: str
    log_id: int | None = None
    user_id: str | None = None
    user_choice: Choice
    choice_at: str
    trusted_added: bool
    message_ar: str
    final_status: str | None = Field(
        default=None, description="pending / completed / cancelled لتحويل المحفظة"
    )
    receipt: dict | None = Field(default=None, description="إيصال Zain Cash بعد التنفيذ")


class WalletTransferResponse(AssessResponse):
    """نتيجة اعتراض التحويل: نُفّذ فوراً أو عُلّق بانتظار /api/choice."""

    status: Literal["executed", "blocked"]
    receipt: dict | None = Field(default=None, description="إيصال Zain Cash (عند allow فقط)")
    cooling_off_seconds: int | None = Field(
        default=None, description="فترة التهدئة قبل ما يكمل المستخدم (10 ثواني)"
    )
    final_status: str | None = Field(default=None, description="completed أو pending")


class ScenarioTextResponse(BaseModel):
    """نتيجة /api/scenario_text (T6): تقييم، أو سؤال توضيحي، أو رسالة آمنة."""

    status: Literal["assessed", "needs_clarification", "cannot_parse"]
    message_ar: str = Field(default="", description="السؤال التوضيحي أو رسالة الخطأ")
    extracted: dict | None = Field(default=None, description="الحقائق المستخرجة من النص")
    intake_source: str | None = Field(default=None, description="json أو llm")
    assessment: AssessResponse | None = Field(
        default=None, description="نتيجة الكشف (عند status=assessed فقط)"
    )


class ChatResponse(BaseModel):
    """جواب الحوار (T11): ≤ 50 كلمة — لا يغيّر القرار أبداً."""

    tx_id: str
    turn: int = Field(description="رقم الجولة (1..5)")
    reply_ar: str
    source: str = Field(description="template / llm / limit")
    turns_used: int = Field(description="كم رسالة مستخدم مسجّلة بالفعل")
    limit_reached: bool = Field(default=False, description="انوصل للحد: 5 رسائل")


# ------------------------------------------------------------------ /api/training (T12)
class TrainingStartRequest(ApiModel):
    """بداية سيناريو تدريبي — بلا نص حر وبلا أي بيانات مستخدم."""

    scenario_id: str | None = Field(
        default=None, max_length=MAX_ID,
        description="سيناريو معروف، أو الأعلى تلقائياً",
    )
    use_llm: bool = Field(default=False, description="صوت المحادثة بالـ LLM")


class TrainingAnswerRequest(ApiModel):
    """إجابة تراكمية: كل الإجابات من أول سطر حتى الأخير (بلا حالة بالخادم)."""

    scenario_id: str = Field(max_length=MAX_ID)
    answers: list[Literal["flag", "continue"]] = Field(
        min_length=1, max_length=20,
        description="flag=هذا احتيال / continue=أكمل — enums فقط (بلا نص حر)",
    )
    use_llm: bool = Field(default=False, description="صوت المحادثة بالـ LLM")


class TrainingEvaluation(BaseModel):
    """تقييم بسيط بعد نهاية السيناريو (T12)."""

    correct: int
    total: int
    score_pct: int = Field(ge=0, le=100)
    verdict_ar: str = Field(description="ممتاز / زين / متوسط / ضعيف")
    feedback_ar: str = Field(description="تعليق باللهجة العراقية")


class TrainingResponse(BaseModel):
    """رد التدريب: معلن "تدريب" بكل حالة (T12)."""

    scenario_id: str
    title_ar: str
    training_notice_ar: str
    status: Literal["playing", "finished"]
    turn: int = Field(description="رقم السطر الحالي (1..N)")
    total_turns: int
    line_ar: str = Field(default="", description="سطر المحادثة (فارغ عند finish)")
    line_source: str = Field(default="script", description="script / llm")
    evaluation: TrainingEvaluation | None = None


class UserOut(BaseModel):
    user_id: str
    name: str | None = None
    archetype: str | None = None
    split: str
    n_tx: int = 0
    last_ts: str | None = None


class UserListResponse(BaseModel):
    count: int
    users: list[UserOut]


class ProfileResponse(BaseModel):
    user_id: str
    name: str | None = None
    archetype: str | None = None
    as_of: str
    profile: dict


class LogRow(BaseModel):
    log_id: int
    tx_id: str | None
    user_id: str | None
    created_at: str
    risk_score: int | None
    decision: Decision | None
    reasons: list[ReasonOut]
    matched_pattern: str | None
    coaching_message: str | None
    coaching_source: str | None
    user_choice: str | None
    choice_at: str | None
    rules_version: str | None
    final_status: str | None = Field(
        default=None, description="pending / completed / cancelled (تحويل المحفظة)"
    )
    receipt: dict | None = None


class LogResponse(BaseModel):
    count: int
    rows: list[LogRow]


class ExportResponse(BaseModel):
    rows: int
    jsonl_path: str
    csv_path: str
    jsonl_url: str
    csv_url: str


class EvalResponse(BaseModel):
    available: bool
    generated_at: str | None = None
    split: str | None = None
    rules_version: str | None = None
    hint_ar: str
    results: dict | None = None
