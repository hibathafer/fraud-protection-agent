"""طبقة الاعتراض بين محفظة Zain Cash وخدمة التحويل.

الترتيب المفروض (مطلوب في المهمة):
    طلب التحويل → الكشف (engine) + التوعية (coach) → route() هنا
    → allow: تنفيذ فوري عبر zain_cash
    → warn/hold: تعليق + فترة تهدئة 10 ثواني + انتظار POST /api/choice

الطلب المعلّق (بما فيه الرمز السري) يبقى بالذاكرة فقط: ما ينكتب بالسجل
ولا بملف ولا بقاعدة البيانات.
"""

from src.integrations import zain_cash

COOLING_OFF_SECONDS = 10

_PENDING: dict = {}


def hold_pending(tx_id: str, request: dict) -> None:
    """يعلّق طلب تحويل بانتظار قرار المستخدم (warn/hold فقط)."""
    _PENDING[tx_id] = dict(request)


def take_pending(tx_id: str) -> dict | None:
    """يخرج الطلب المعلّق (مرة وحدة) ويرجعه، أو None إذا ماكو."""
    return _PENDING.pop(str(tx_id), None)


def clear_pending() -> None:
    """يمسح كل المعلّق (الاختبارات)."""
    _PENDING.clear()


def pending_count() -> int:
    return len(_PENDING)


def execute(request: dict) -> dict:
    """ينفذ التحويل المعلّق عبر المحفظة الوهمية."""
    return zain_cash.initiate_zain_cash_transfer(
        request["sender_msisdn"],
        request["recipient_msisdn"],
        request["amount_iqd"],
        request["pin"],
    )


def route(decision: str, transfer_request: dict, tx_id: str) -> dict:
    """التوجيه بعد الكشف:
    - allow    → ينفذ حالاً ويرجع الإيصال
    - warn/hold → يعلّق ويطلب فترة تهدئة قبل اختيار المستخدم
    """
    if decision == "allow":
        return {"action": "execute", "receipt": execute(transfer_request)}
    hold_pending(tx_id, transfer_request)
    return {"action": "block", "cooling_off_seconds": COOLING_OFF_SECONDS}
