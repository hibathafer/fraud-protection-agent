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
