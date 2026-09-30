"""اختبارات إحصاءات المستخدم: أهمها عدم التسريب من المستقبل (7.1)."""

from datetime import timedelta

from src.detection.features import build_profile, parse_ts

NOW = "2026-10-20T14:00:00+03:00"
NOW_DT = parse_ts(NOW)


def at(days_ago=0, hours_ago=0, hour=None):
    """طابع وقت قبل اللحظة، مع ساعة محددة إذا طلبنا."""
    dt = NOW_DT - timedelta(days=days_ago, hours=hours_ago)
    return dt.replace(hour=hour, minute=0, second=0).isoformat() if hour else dt.isoformat()


def row(ts, amount, recipient="r1", tx_type="transfer", **extra):
    r = {"ts": ts, "amount_iqd": amount, "recipient_id": recipient, "tx_type": tx_type}
    r.update(extra)
    return r


def history_before(n=10, amount=100_000, recipient="r1", hours_ago=48):
    """n معاملات قبل اللحظة، كل وحدة 3 ساعات."""
    return [row(at(hours_ago=hours_ago + i * 3), amount, recipient) for i in range(n)]


def test_counts_only_past_transactions():
    future = [row(at(hours_ago=-h), 9_000_000) for h in (1, 2, 3)]
    profile = build_profile(history_before(10) + future, NOW)
    assert profile["n_tx"] == 10


def test_no_leakage_from_future_amounts():
    """مبالغ المستقبل ما تأثر على median/p95."""
    past = history_before(10, amount=100_000)
    future = [row(at(hours_ago=-h), 9_000_000) for h in (1, 2, 3)]
    clean, dirty = build_profile(past, NOW), build_profile(past + future, NOW)
    assert dirty["median_amount"] == clean["median_amount"] == 100_000
    assert dirty["p95_amount"] == clean["p95_amount"] == 100_000


def test_no_leakage_from_future_recipients():
    """مستلمو ما بعد اللحظة ما يدخلون بقائمة الجهات المعروفة."""
    future = [row(at(hours_ago=-1), 50_000, recipient="r_future")]
    profile = build_profile(history_before(10) + future, NOW)
    assert "r_future" not in profile["known_recipients"]


def test_no_leakage_from_ground_truth():
    """تغيير is_scam / scam_type / case_id ما يغيّر أي إحصاء."""
    past = history_before(10)
    tampered = [dict(r, is_scam=1, scam_type="prize_fee", case_id="c_fake") for r in past]
    assert build_profile(tampered, NOW) == build_profile(past, NOW)


def test_median_and_p95():
    amounts = [10_000, 20_000, 30_000, 40_000, 5_000_000]
    rows = [row(at(days_ago=i + 1), a) for i, a in enumerate(amounts)]
    profile = build_profile(rows, NOW)
    assert profile["n_tx"] == 5
    assert profile["median_amount"] == 30_000
    assert profile["p95_amount"] == 5_000_000  # أقرب رتبة


def test_typical_hours_includes_dominant_hour():
    rows = [row(at(days_ago=i + 1, hour=14), 100_000) for i in range(20)]
    profile = build_profile(rows, NOW)
    assert profile["typical_hours"] == [14]


def test_typical_hours_excludes_rare_hour():
    # 20 معاملة الساعة 14 + وحدة الساعة 3 => 1/21 = 4.7% أقل من 5% => مو مألوفة
    rows = [row(at(days_ago=i + 1, hour=14), 100_000) for i in range(20)]
    rare = row(at(hours_ago=2, hour=3), 100_000)
    profile = build_profile(rows + [rare], NOW)
    assert profile["n_tx"] == 21
    assert profile["typical_hours"] == [14]


def test_recent_tx_30min_counts_transfers_only():
    rows = [
        row(NOW_DT.replace(hour=13, minute=50).isoformat(), 50_000),
        row(NOW_DT.replace(hour=13, minute=40).isoformat(), 50_000),
        row(NOW_DT.replace(hour=13, minute=10).isoformat(), 50_000, tx_type="bill"),
    ]
    profile = build_profile(rows, NOW)
    assert profile["n_tx"] == 3
    assert profile["recent_tx_30min"] == 2  # الفاتورة ما تحسب تحويل


def test_recent_tx_30min_excludes_older_than_window():
    # النافذة 13:30–14:00، فـ 13:20 و 12:50 برّا
    rows = [
        row(NOW_DT.replace(hour=13, minute=55).isoformat(), 50_000),
        row(NOW_DT.replace(hour=13, minute=20).isoformat(), 50_000),
        row(NOW_DT.replace(hour=12, minute=50).isoformat(), 50_000),
    ]
    assert build_profile(rows, NOW)["recent_tx_30min"] == 1


def test_sent_to_recipient_7d_sum_and_count():
    rows = [
        row(at(days_ago=1), 20_000, recipient="r2"),
        row(at(days_ago=3), 30_000, recipient="r2"),
        row(at(days_ago=20), 999_000, recipient="r2"),  # أقدم من 7 أيام => يُهمل
        row(at(days_ago=2), 15_000, recipient="r3"),
    ]
    profile = build_profile(rows, NOW, recipient_id="r2")
    assert profile["sent_to_recipient_7d"] == {"count": 2, "sum_iqd": 50_000}


def test_recipient_history_and_span():
    rows = [
        row(at(days_ago=20), 10_000, recipient="r2"),
        row(at(days_ago=10), 10_000, recipient="r2"),
        row(at(days_ago=1), 10_000, recipient="r2"),
    ]
    profile = build_profile(rows, NOW, recipient_id="r2")
    assert profile["recipient"]["count"] == 3
    assert profile["recipient"]["is_new"] is False
    assert 19 <= profile["recipient"]["span_days"] <= 20


def test_recipient_is_new_when_unknown():
    profile = build_profile(history_before(10), NOW, recipient_id="r_unknown")
    assert profile["recipient"]["count"] == 0
    assert profile["recipient"]["is_new"] is True
    assert profile["recipient"]["first_ts"] is None


def test_trusted_flag_comes_from_list():
    rows = history_before(10)
    assert build_profile(rows, NOW, recipient_id="r1", trusted_recipients=["r1"])["trusted"] is True
    assert build_profile(rows, NOW, recipient_id="r1", trusted_recipients=[])["trusted"] is False


def test_empty_history_gives_empty_profile():
    profile = build_profile([], NOW, recipient_id="r_new")
    assert profile["n_tx"] == 0
    assert profile["median_amount"] == 0.0
    assert profile["p95_amount"] == 0.0
    assert profile["typical_hours"] == []
    assert profile["recent_tx_30min"] == 0
