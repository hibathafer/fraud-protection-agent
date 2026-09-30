"""محرّك الكشف (7.3): يجمع القواعد ويطلع score + decision.

القاعدة الذهبية: القرار من القواعد فقط. ممنوع يقرأ is_scam / scam_type / case_id.
"""

from src.config import HOLD_SCORE, RULES_VERSION, SCORE_MAX, WARN_SCORE
from src.detection.rules import RULES, rule_scam_pattern, rule_trusted_recipient


def score_to_decision(score: int) -> str:
    """allow < 30 <= warn < 60 <= hold."""
    if score < WARN_SCORE:
        return "allow"
    return "hold" if score >= HOLD_SCORE else "warn"


def assess(tx, profile, catalogue=None) -> dict:
    """يقيّم معاملة واحدة ويرجع النتيجة الكاملة.

    tx: معاملة (note, context_message, amount_iqd, balance_before_iqd, ts,
    tx_type, recipient_id, recipient_age_days)
    profile: ناتج features.build_profile لنفس المستخدم ونفس الوقت
    """
    reasons = []
    for rule in RULES:
        if rule is rule_trusted_recipient:
            continue  # نطبقها بعد ما نعرف إذا طابق النص نمط معروف
        result = rule(tx, profile)
        if result:
            reasons.append(result)

    matched = rule_scam_pattern(tx, profile, catalogue)
    pattern_reason, pattern = matched if matched else (None, None)
    if pattern_reason:
        reasons.append(pattern_reason)
    else:
        # TRUSTED_RECIPIENT ما تنطبق إذا صار تطابق SCAM_PATTERN (7.2)
        trusted = rule_trusted_recipient(tx, profile)
        if trusted:
            reasons.append(trusted)

    raw = sum(r.points for r in reasons)
    score = max(0, min(SCORE_MAX, raw))
    reasons.sort(key=lambda r: -abs(r.points))
    return {
        "score": score,
        "raw_score": raw,
        "decision": score_to_decision(score),
        "reasons": [r.to_dict() for r in reasons],
        "matched_pattern": pattern["id"] if pattern else None,
        "pattern": pattern,
        "rules_version": RULES_VERSION,
    }
