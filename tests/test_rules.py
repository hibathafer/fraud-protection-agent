"""اختبار لكل قاعدة: حالة تتحقق وحالة ما تتحقق (7.2 و17)."""

from datetime import timedelta

from src.detection.features import build_profile, parse_ts
from src.detection.rules import (
    RULES,
    rule_amount_high,
    rule_balance_drain,
    rule_cumulative_new_recipient,
    rule_new_recipient,
    rule_odd_hour,
    rule_rapid_sequence,
    rule_scam_pattern,
    rule_trusted_recipient,
    rule_young_recipient_account,
)

NOW = "2026-10-20T14:00:00+03:00"
NOW_DT = parse_ts(NOW)


def at(days_ago=0, hours_ago=0, hour=None):
    dt = NOW_DT - timedelta(days=days_ago, hours=hours_ago)
    return dt.replace(hour=hour, minute=0, second=0).isoformat() if hour else dt.isoformat()


def hist(n=12, amount=100_000, recipient="r1", **kw):
    return [
        {"ts": at(days_ago=30, hours_ago=30 - i * 2), "amount_iqd": amount,
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


def profile(history, **kw):
    kw.setdefault("recipient_id", "r1")
    return build_profile(history, NOW, **kw)


# ---------------------------------------------------------------- NEW_RECIPIENT
def test_new_recipient_fires_for_unknown_recipient():
    r = rule_new_recipient(tx(recipient_id="r_new"), profile(hist(), recipient_id="r_new"))
    assert r and r.rule_id == "NEW_RECIPIENT" and r.points == 20
    assert "أول مرة" in r.text_ar


def test_new_recipient_silent_for_known_recipient():
    assert rule_new_recipient(tx(), profile(hist())) is None


# ------------------------------------------------------- YOUNG_RECIPIENT_ACCOUNT
def test_young_recipient_fires_for_new_and_young():
    r = rule_young_recipient_account(
        tx(recipient_id="r_new", recipient_age_days=3), profile(hist(), recipient_id="r_new")
    )
    assert r and r.rule_id == "YOUNG_RECIPIENT_ACCOUNT" and r.points == 15


def test_young_recipient_silent_when_account_is_old_or_recipient_known():
    assert rule_young_recipient_account(
        tx(recipient_id="r_new", recipient_age_days=200), profile(hist(), recipient_id="r_new")
    ) is None
    assert rule_young_recipient_account(tx(recipient_age_days=2), profile(hist())) is None


# ---------------------------------------------------------------- AMOUNT_HIGH
def test_amount_high_fires_above_three_times_median():
    r = rule_amount_high(tx(amount_iqd=400_000), profile(hist()))
    assert r and r.rule_id == "AMOUNT_HIGH" and r.points == 25


def test_amount_high_silent_within_normal_range():
    assert rule_amount_high(tx(amount_iqd=150_000), profile(hist())) is None


def test_amount_high_uses_fixed_threshold_for_short_history():
    short = hist(n=5)
    assert rule_amount_high(tx(amount_iqd=400_000), profile(short)) is not None   # فوق 300,000
    assert rule_amount_high(tx(amount_iqd=250_000), profile(short)) is None      # تحت 300,000


def test_amount_high_uses_p95_when_higher():
    rows = hist(n=12, amount=100_000) + [
        {"ts": at(days_ago=1), "amount_iqd": 2_000_000, "recipient_id": "r1", "tx_type": "transfer"}
    ]
    assert rule_amount_high(tx(amount_iqd=1_500_000), profile(rows)) is not None


# ---------------------------------------------------------------- BALANCE_DRAIN
def test_balance_drain_fires_at_seventy_percent():
    r = rule_balance_drain(tx(amount_iqd=700_000, balance_before_iqd=1_000_000), profile(hist()))
    assert r and r.rule_id == "BALANCE_DRAIN" and r.points == 15


def test_balance_drain_silent_below_threshold():
    assert rule_balance_drain(
        tx(amount_iqd=600_000, balance_before_iqd=1_000_000), profile(hist())
    ) is None


# ---------------------------------------------------------------- ODD_HOUR
def test_odd_hour_fires_at_3am_for_a_day_user():
    night = hist(n=10) + [
        {"ts": at(days_ago=1, hour=14), "amount_iqd": 100_000, "recipient_id": "r1", "tx_type": "transfer"}
    ]
    r = rule_odd_hour(tx(ts=at(hour=3), amount_iqd=100_000), profile(night))
    assert r and r.rule_id == "ODD_HOUR" and r.points == 10


def test_odd_hour_silent_for_night_owl():
    night = hist(n=10) + [
        {"ts": at(days_ago=1, hour=3), "amount_iqd": 100_000, "recipient_id": "r1", "tx_type": "transfer"}
    ]
    assert rule_odd_hour(tx(ts=at(hour=3), amount_iqd=100_000), profile(night)) is None


# ---------------------------------------------------------------- RAPID_SEQUENCE
def test_rapid_sequence_fires_with_two_recent_transfers():
    rows = hist(n=10) + [
        {"ts": NOW_DT.replace(hour=13, minute=55).isoformat(),
         "amount_iqd": 50_000, "recipient_id": "r1", "tx_type": "transfer"},
        {"ts": NOW_DT.replace(hour=13, minute=45).isoformat(),
         "amount_iqd": 50_000, "recipient_id": "r1", "tx_type": "transfer"},
    ]
    r = rule_rapid_sequence(tx(ts=NOW, amount_iqd=50_000), profile(rows))
    assert r and r.rule_id == "RAPID_SEQUENCE" and r.points == 15


def test_rapid_sequence_silent_when_alone():
    assert rule_rapid_sequence(tx(ts=NOW, amount_iqd=50_000), profile(hist(n=10))) is None


# ---------------------------------------------------------------- SCAM_PATTERN
def test_scam_pattern_fires_on_catalogue_message():
    result = rule_scam_pattern(
        tx(note=None, context_message="موظف الدعم يطلب رمز تحقق منك"), profile(hist())
    )
    reason, pattern = result
    assert reason.rule_id == "SCAM_PATTERN" and reason.points == 35
    assert pattern["id"] == "otp_fake_agent"
    assert "نمط" in reason.text_ar


def test_scam_pattern_silent_on_normal_note():
    assert rule_scam_pattern(tx(note="راتب الشهر"), profile(hist())) is None


def test_scam_pattern_uses_pattern_weight():
    result = rule_scam_pattern(
        tx(context_message="مبروك ربحت الجائزة، حول رسوم المعالجة"), profile(hist())
    )
    reason, _ = result
    assert reason.rule_id == "SCAM_PATTERN"


# ---------------------------------------------------- CUMULATIVE_NEW_RECIPIENT
def test_cumulative_new_recipient_fires_on_slow_scam():
    # مستلم شففناه أول مرة قبل يومين، 3 تحويلات بآخر 7 أيام ومجموعها فوق 2×median
    rows = hist(n=12) + [
        {"ts": at(days_ago=2), "amount_iqd": 150_000, "recipient_id": "r_scam", "tx_type": "transfer"},
        {"ts": at(days_ago=1), "amount_iqd": 250_000, "recipient_id": "r_scam", "tx_type": "transfer"},
    ]
    r = rule_cumulative_new_recipient(
        tx(recipient_id="r_scam", amount_iqd=400_000), profile(rows, recipient_id="r_scam")
    )
    assert r and r.rule_id == "CUMULATIVE_NEW_RECIPIENT" and r.points == 20


def test_cumulative_new_recipient_silent_for_established_recipient():
    rows = hist(n=12) + [
        {"ts": at(days_ago=30), "amount_iqd": 25_000, "recipient_id": "r_old", "tx_type": "transfer"},
        {"ts": at(days_ago=25), "amount_iqd": 40_000, "recipient_id": "r_old", "tx_type": "transfer"},
    ]
    r = rule_cumulative_new_recipient(
        tx(recipient_id="r_old", amount_iqd=60_000), profile(rows, recipient_id="r_old")
    )
    assert r is None  # أول تحويل له قبل أكثر من أسبوع => مو "جديد"


def test_cumulative_new_recipient_silent_for_first_transfer():
    assert rule_cumulative_new_recipient(
        tx(recipient_id="r_new", amount_iqd=500_000), profile(hist(), recipient_id="r_new")
    ) is None


# ---------------------------------------------------------------- TRUSTED_RECIPIENT
def test_trusted_recipient_fires_with_long_history():
    rows = hist(n=12) + [
        {"ts": at(days_ago=40), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
        {"ts": at(days_ago=20), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"},
    ]
    r = rule_trusted_recipient(tx(), profile(rows))
    assert r and r.rule_id == "TRUSTED_RECIPIENT" and r.points == -25


def test_trusted_recipient_fires_from_trusted_list():
    r = rule_trusted_recipient(tx(recipient_id="r_fav"), profile(hist(), recipient_id="r_fav",
                                                                    trusted_recipients=["r_fav"]))
    assert r and r.points == -25


def test_trusted_recipient_silent_for_recent_recipient():
    # r1 شففناه مرة وحدة قبل يومين => ما تاريخ طويل وياه
    rows = hist(n=12, recipient="r_other") + [
        {"ts": at(days_ago=2), "amount_iqd": 90_000, "recipient_id": "r1", "tx_type": "transfer"}
    ]
    assert rule_trusted_recipient(tx(), profile(rows)) is None


def test_all_nine_rules_are_defined_and_weighted():
    from src.config import POINTS

    assert len(RULES) == 7  # المحرك ينادي القاعدتين المتبقيتين
    assert rule_trusted_recipient not in RULES
    assert len(POINTS) == 9
    assert set(POINTS) == {
        "NEW_RECIPIENT", "YOUNG_RECIPIENT_ACCOUNT", "AMOUNT_HIGH", "BALANCE_DRAIN",
        "ODD_HOUR", "RAPID_SEQUENCE", "SCAM_PATTERN", "CUMULATIVE_NEW_RECIPIENT",
        "TRUSTED_RECIPIENT",
    }
