"""إحصاءات المستخدم (7.1) — محسوبة من المعاملات السابقة للحالية فقط.

ممنوع يقرأ is_scam / scam_type / case_id. الدالة نقية: تعطي نفس النتيجة لنفس المدخلات.
"""

from datetime import datetime, timedelta
from statistics import median

from src.config import BAGHDAD_TZ, CUMULATIVE_DAYS, RAPID_WINDOW_MINUTES, TYPICAL_HOURS_SHARE


def parse_ts(ts) -> datetime:
    """ISO => datetime بتوقيت بغداد إذا ما كان فيه offset."""
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=BAGHDAD_TZ)


def _percentile(values, q: float) -> float:
    """أقرب رتبة: يرجع القيمة عند النسبة q من 0 إلى 1."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = round(q * (len(ordered) - 1))
    return float(ordered[max(0, min(len(ordered) - 1, idx))])


def build_profile(history, ts, recipient_id=None, trusted_recipients=None) -> dict:
    """ملف المستخدم وقت معاملة certain.

    history: كل معاملات المستخدم (من CSV/DB/JSON) — نقرأ منها ts, amount_iqd,
    tx_type, recipient_id فقط. أي معاملة بعد ts تُهمل (قاعدة بدون تسريب).
    """
    now = parse_ts(ts)
    window_30 = now - timedelta(minutes=RAPID_WINDOW_MINUTES)
    window_7d = now - timedelta(days=CUMULATIVE_DAYS)
    trusted = set(trusted_recipients or [])

    past = []
    for row in history:
        row_ts = parse_ts(row["ts"])
        if row_ts < now:  # شرط عدم التسريب: الماضي فقط
            past.append((row_ts, row))

    amounts = [int(r["amount_iqd"]) for _, r in past]
    known = {}
    hour_counts = {}
    recent_30 = 0
    for row_ts, row in past:
        rid = row.get("recipient_id")
        is_transfer = row.get("tx_type", "transfer") == "transfer"
        info = known.setdefault(
            rid, {"count": 0, "first_ts": None, "last_ts": None, "total_iqd": 0}
        )
        info["count"] += 1
        info["total_iqd"] += int(row["amount_iqd"])
        if info["first_ts"] is None or row_ts < info["first_ts"]:
            info["first_ts"] = row_ts
        if info["last_ts"] is None or row_ts > info["last_ts"]:
            info["last_ts"] = row_ts
        hour_counts[row_ts.hour] = hour_counts.get(row_ts.hour, 0) + 1
        if is_transfer and row_ts >= window_30:
            recent_30 += 1

    n_tx = len(past)
    typical_hours = sorted(
        h for h, c in hour_counts.items() if n_tx and c / n_tx >= TYPICAL_HOURS_SHARE
    )

    recipient = {"count": 0, "first_ts": None, "last_ts": None, "span_days": 0.0, "is_new": True}
    sent_7d = {"count": 0, "sum_iqd": 0}
    if recipient_id is not None:
        info = known.get(recipient_id)
        if info:
            span = (info["last_ts"] - info["first_ts"]).total_seconds() / 86400
            recipient = {
                "count": info["count"],
                "first_ts": info["first_ts"],
                "last_ts": info["last_ts"],
                "span_days": span,
                "is_new": False,
            }
        # تحويلات هذا المستلم بآخر 7 أيام (بدون المعاملة الحالية)
        for row_ts, row in past:
            if (
                row.get("recipient_id") == recipient_id
                and row.get("tx_type", "transfer") == "transfer"
                and row_ts >= window_7d
            ):
                sent_7d["count"] += 1
                sent_7d["sum_iqd"] += int(row["amount_iqd"])

    return {
        "as_of": now.isoformat(),
        "n_tx": n_tx,
        "median_amount": float(median(amounts)) if amounts else 0.0,
        "p95_amount": _percentile(amounts, 0.95),
        "typical_hours": typical_hours,
        "known_recipients": known,
        "recent_tx_30min": recent_30,
        "sent_to_recipient_7d": sent_7d,
        "recipient": recipient,
        "trusted": recipient_id in trusted if recipient_id is not None else False,
    }
