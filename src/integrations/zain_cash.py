"""عميل Zain Cash وهمي (mock) لواجهة التحويل.

القاعدة: ما فيه نداء حقيقي لأي API. الدالة تحاكي رد الخدمة حتى الديمو
يشتغل بدون نت. الرمز السري (pin) يُتحقق منه هنا فقط: ما ينحفظ، ما ينطبع،
وما يمر للكشف ولا للـ LLM.
"""

import re
import uuid
from datetime import datetime

from src.config import BAGHDAD_TZ

MSISDN_PATTERN = r"^07\d{9}$"
PIN_PATTERN = r"^\d{4,6}$"
MAX_TRANSFER_IQD = 10_000_000_000


class ZainCashError(ValueError):
    """خطأ برحلة التحويل (مدخل غير صالح أو مرفوض من الخدمة)."""


def validate_msisdn(value, field_ar: str = "رقم الهاتف") -> str:
    msisdn = str(value or "").strip()
    if not re.match(MSISDN_PATTERN, msisdn):
        raise ZainCashError(f"{field_ar} لازم يكون 11 رقم يبدأ بـ 07 مثل 0770123456")
    return msisdn


def mask_msisdn(value) -> str:
    """يخفي وسط الرقم: 0770****456 (خصوصية بالإيصالات)."""
    s = str(value or "")
    return f"{s[:4]}****{s[-3:]}"


def validate_amount(amount_iqd) -> int:
    try:
        amount = int(amount_iqd)
    except (TypeError, ValueError) as exc:
        raise ZainCashError("المبلغ لازم يكون رقماً بالدينار") from exc
    if amount <= 0:
        raise ZainCashError("المبلغ لازم يكون أكبر من صفر")
    if amount > MAX_TRANSFER_IQD:
        raise ZainCashError("المبلغ يتجاوز حد التحويل المسموح")
    return amount


def validate_pin(pin) -> str:
    value = str(pin or "")
    if not re.match(PIN_PATTERN, value):
        raise ZainCashError("الرمز السري لازم يكون 4 إلى 6 أرقام")
    return value  # نرجعه ما نخزنه: يمر ويُهمل بعد التحقق


def initiate_zain_cash_transfer(sender_msisdn, recipient_msisdn, amount_iqd, pin) -> dict:
    """يحاكي تنفيذ التحويل ويرجع إيصالاً. لا ينادي أي API حقيقي.

    التحقق هنا هو آخر خط دفاع — الكشف والتوعية صاروا قبل هذا السطر.
    """
    sender = validate_msisdn(sender_msisdn, "رقم المرسل")
    recipient = validate_msisdn(recipient_msisdn, "رقم المستلم")
    amount = validate_amount(amount_iqd)
    validate_pin(pin)  # يتحقق ويرمي: ما نحتاج قيمته بعد كذا
    if sender == recipient:
        raise ZainCashError("رقم المستلم لازم يختلف عن رقم المرسل")

    return {
        "status": "success",
        "receipt_id": "ZC" + uuid.uuid4().hex[:10].upper(),
        "sender_msisdn_masked": mask_msisdn(sender),
        "recipient_msisdn_masked": mask_msisdn(recipient),
        "amount_iqd": amount,
        "currency": "IQD",
        "fee_iqd": 0,
        "ts": datetime.now(BAGHDAD_TZ).isoformat(timespec="seconds"),
        "channel": "mock_api",
    }
