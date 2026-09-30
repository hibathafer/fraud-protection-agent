"""اختبار metrics.py بأرقام تنحسب يدوياً (12.1) — ما فيه أي اعتماد على البيانات."""

import pytest

from src.eval.metrics import macro_recall, metrics, recall_by_group


def test_metrics_hand_computed():
    # 8 معاملات: 3 احتيال + 5 بريء
    # التنبيه الوحيد على احتيال واحد (المركز 2) وعلى بريء واحد (المركز 5)
    # => TP=1, FP=1, FN=2, TN=4
    y_true = [1, 1, 1, 0, 0, 0, 0, 0]
    y_pred = [0, 1, 0, 0, 1, 0, 0, 0]

    m = metrics(y_true, y_pred)

    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 2, 4)
    assert m["n"] == 8
    assert m["scam_total"] == 3
    assert m["legit_total"] == 5
    assert m["alerted"] == 2
    assert m["precision"] == pytest.approx(1 / 2)      # 1/(1+1)
    assert m["recall"] == pytest.approx(1 / 3)         # 1/(1+2)
    assert m["fpr"] == pytest.approx(1 / 5)            # 1/(1+4)


def test_metrics_perfect_and_useless():
    perfect = metrics([1, 0, 1, 0], [1, 0, 1, 0])
    assert (perfect["precision"], perfect["recall"], perfect["fpr"]) == (1.0, 1.0, 0.0)
    assert (perfect["tp"], perfect["fp"], perfect["fn"], perfect["tn"]) == (2, 0, 0, 2)

    # يحذّر على كل شي: recall كامل بس precision وFPR سيئين (12.3 يشرح هالشي)
    alarm = metrics([1, 0, 1, 0], [1, 1, 1, 1])
    assert (alarm["tp"], alarm["fp"], alarm["fn"], alarm["tn"]) == (2, 2, 0, 0)
    assert alarm["precision"] == pytest.approx(0.5)
    assert alarm["recall"] == pytest.approx(1.0)
    assert alarm["fpr"] == pytest.approx(1.0)

    # ما يحذّر أبداً: FN كل الاحتيال، وFPR صفر مو خطأ
    silent = metrics([1, 0, 1, 0], [0, 0, 0, 0])
    assert silent["precision"] == 0.0                 # ما فيه تنبيهات => القسمة على صفر
    assert silent["recall"] == 0.0
    assert silent["fpr"] == 0.0
    assert (silent["fn"], silent["tn"]) == (2, 2)


def test_metrics_length_mismatch():
    with pytest.raises(ValueError):
        metrics([1, 0, 1], [1, 0])


def test_recall_by_group_hand_computed():
    # لكل نوع 4 معاملات: 2 احتيال + 2 بريء
    y_true = [1, 1, 0, 0, 1, 0, 1, 1]
    y_pred = [1, 0, 0, 1, 1, 0, 0, 0]
    groups = ["prize_fee", "prize_fee", "prize_fee", "prize_fee",
              "safe_account", "safe_account", "safe_account", "safe_account"]

    per_type = recall_by_group(y_true, y_pred, groups)

    # prize_fee: TP=1, FN=1 من 2 احتيال من النوع => recall 1/2
    # safe_account: TP=1, FN=2 من 3 احتيال من النوع => recall 1/3
    assert per_type["prize_fee"] == {
        "tp": 1, "fn": 1, "n": 4, "scam_total": 2, "recall": pytest.approx(0.5)
    }
    assert per_type["safe_account"] == {
        "tp": 1, "fn": 2, "n": 4, "scam_total": 3, "recall": pytest.approx(1 / 3)
    }
    assert set(per_type) == {"prize_fee", "safe_account"}
    assert macro_recall(per_type) == pytest.approx((0.5 + 1 / 3) / 2)


def test_recall_by_group_type_sorted_from_weak_to_strong():
    y_true = [1, 1, 1, 1]
    y_pred = [0, 0, 1, 1]  # نوع ضعيف 0%، نوع قوي 100%
    groups = ["weak", "weak", "strong", "strong"]

    per_type = recall_by_group(y_true, y_pred, groups)
    ordered = sorted(per_type, key=lambda name: per_type[name]["recall"])

    assert ordered == ["weak", "strong"]
    assert macro_recall(per_type) == pytest.approx(0.5)
    assert macro_recall({}) == 0.0


def test_recall_by_group_length_mismatch():
    with pytest.raises(ValueError):
        recall_by_group([1, 0], [1, 0], ["only_one_group"])
