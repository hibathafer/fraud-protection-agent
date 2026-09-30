"""اختبارات المحرك: العتبات، ترتيب النقاط، وما يقرأ من المعاملة (7.3 و17)."""

from datetime import timedelta

from src.detection.engine import assess, score_to_decision
from src.detection.features import build_profile, parse_ts

NOW = "2026-10-20T14:00:00+03:00"
NOW_DT = parse_ts(NOW)


def at(days_ago=0, hour=None):
    dt = NOW_DT - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0).isoformat() if hour else dt.isoformat()


def hist(n=12, amount=100_000, recipient="r1"):
    return [
        {"ts": at(days_ago=30, hour=14), "amount_iqd": amount,
         "recipient_id": recipient, "tx_type": "transfer"}
        for i in range(n)
    ]


def tx(**kw):
    base = {
        "ts": NOW, "amount_iqd": 100_000, "balance_before_iqd": 5_000_000,
        "tx_type": "transfer", "recipient_id": "r1", "recipient_age_days": 400,
        "note": None, "context_message": None,
    }
    base.update(kw)
    return base


def run(transaction, history=None, **kw):
    history = hist() if history is None else history
    return assess(transaction, build_profile(history, NOW, transaction["recipient_id"], **kw))


def test_score_to_decision_thresholds():
    assert score_to_decision(0) == "allow"
    assert score_to_decision(29) == "allow"
    assert score_to_decision(30) == "warn"
    assert score_to_decision(59) == "warn"
    assert score_to_decision(60) == "hold"
    assert score_to_decision(100) == "hold"


def test_normal_transfer_is_allowed():
    result = run(tx())
    assert result["decision"] == "allow"
    assert result["score"] == 0
    assert result["reasons"] == []
    assert result["matched_pattern"] is None


def test_new_recipient_with_normal_amount_is_allowed():
    """20 نقطة أقل من عتبة التنبيه: مستلم جديد بمبلغ اعتيادي =يمر (نقطة ضعف موثقة)."""
    result = run(tx(recipient_id="r_new"), hist())
    assert result["score"] == 20
    assert result["decision"] == "allow"


def test_new_young_recipient_with_high_amount_warns():
    result = run(tx(recipient_id="r_new", recipient_age_days=2, amount_iqd=800_000,
                    balance_before_iqd=4_000_000), hist())
    ids = [r["rule_id"] for r in result["reasons"]]
    assert "NEW_RECIPIENT" in ids and "YOUNG_RECIPIENT_ACCOUNT" in ids and "AMOUNT_HIGH" in ids
    assert result["decision"] in ("warn", "hold")


def test_scam_pattern_alone_gives_warn():
    result = run(tx(note=None, context_message="موظف الدعم يطلب رمز تحقق منك"))
    assert result["matched_pattern"] == "otp_fake_agent"
    assert result["score"] == 35
    assert result["decision"] == "warn"


def test_scam_pattern_plus_sequence_gives_hold():
    history = hist() + [
        {"ts": NOW_DT.replace(hour=13, minute=58).isoformat(), "amount_iqd": 50_000,
         "recipient_id": "r1", "tx_type": "transfer"},
        {"ts": NOW_DT.replace(hour=13, minute=50).isoformat(), "amount_iqd": 50_000,
         "recipient_id": "r1", "tx_type": "transfer"},
    ]
    result = run(tx(recipient_id="r_new", recipient_age_days=1,
                    context_message="مبروك ربحت الجائزة، حول رسوم المعالجة"), history)
    assert result["decision"] == "hold"
    assert result["score"] >= 60
    assert result["matched_pattern"] == "prize_fee"


def test_trusted_recipient_is_not_applied_when_pattern_matches():
    history = hist() + [
        {"ts": at(days_ago=40, hour=14), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
        {"ts": at(days_ago=20, hour=14), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
    ]
    trusted_run = run(tx(), history)
    assert "TRUSTED_RECIPIENT" in [r["rule_id"] for r in trusted_run["reasons"]]

    scam_run = run(tx(context_message="أرسل الكود ورمز التحقق بدون تأخير"), history)
    assert "TRUSTED_RECIPIENT" not in [r["rule_id"] for r in scam_run["reasons"]]
    assert scam_run["matched_pattern"] == "otp_fake_agent"


def test_trusted_recipient_reduces_the_score():
    # r_newish شففناه مرة وحدة قبل يومين => ما تاريخ طويل، بس نضيفه لقائمة الموثوقين
    history = hist() + [
        {"ts": at(days_ago=2, hour=14), "amount_iqd": 90_000, "recipient_id": "r_newish", "tx_type": "transfer"}
    ]
    same = tx(recipient_id="r_newish", amount_iqd=500_000, balance_before_iqd=5_000_000)
    plain = run(same, history)
    trusted = run(same, history, trusted_recipients=["r_newish"])
    assert "TRUSTED_RECIPIENT" not in [r["rule_id"] for r in plain["reasons"]]
    assert "TRUSTED_RECIPIENT" in [r["rule_id"] for r in trusted["reasons"]]
    assert plain["score"] - trusted["score"] == 25


def test_score_is_clamped_between_zero_and_hundred():
    loud = tx(recipient_id="r_new", recipient_age_days=1, amount_iqd=9_000_000,
              balance_before_iqd=10_000_000, ts=at(hour=3),
              context_message="الحساب موقوف، حوّل لحساب آمن حتى نكمل الإجراء")
    result = run(loud)
    assert result["raw_score"] > 100
    assert result["score"] == 100


def test_negative_total_is_clamped_to_zero():
    history = hist() + [
        {"ts": at(days_ago=40, hour=14), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
        {"ts": at(days_ago=20, hour=14), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
    ]
    result = run(tx(amount_iqd=10_000, balance_before_iqd=5_000_000), history)
    assert result["score"] == 0
    assert result["raw_score"] == -25


def test_every_reason_has_readable_arabic_text():
    result = run(tx(recipient_id="r_new", recipient_age_days=1, amount_iqd=800_000,
                    balance_before_iqd=4_000_000,
                    context_message="موظف الدعم يطلب رمز تحقق منك"), hist())
    assert result["reasons"]
    for reason in result["reasons"]:
        assert reason["rule_id"] and reason["text_ar"].strip()
        assert any("\u0600" <= ch <= "\u06ff" for ch in reason["text_ar"])  # فيه عربي
        assert isinstance(reason["points"], int)


def test_engine_never_reads_ground_truth():
    """وضع is_scam=1 أو تغيير scam_type ما يغيّر القرار (قاعدة المشروع)."""
    history = hist()
    clean = run(tx(), history)
    tampered_history = [dict(r, is_scam=1, scam_type="prize_fee", case_id="c1") for r in history]
    tampered_tx = dict(tx(), is_scam=1, scam_type="prize_fee", case_id="c1")
    assert run(tampered_tx, tampered_history) == clean
    assert "is_scam" not in str(clean["reasons"])


def test_result_carries_rules_version_and_pattern_details():
    result = run(tx(context_message="أرباح مضمونة، مضاعفة فلوسك خلال شهر"))
    assert result["rules_version"] == "v1"
    assert result["matched_pattern"] == "investment_doubling"
    assert result["pattern"]["typical_next_line_ar"]
    assert result["pattern"]["advice_ar"]
