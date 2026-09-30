"""مقاييس التقييم (12.1 و12.2) — دوال نقية: ما تقرأ ملفات، ما تطبع، ما تسجّل.

مصدر الأرقام:
- TP: احتيال وانتبه له النظام. FP: بريء وانتبه. FN: احتيال فات. TN: بريء ومرّ.
- precision = TP / (TP + FP)   من التنبيهات، كم كان احتيال حقيقي.
- recall    = TP / (TP + FN)   من الاحتيال الحقيقي، كم انمسك.
- fpr       = FP / (FP + TN)   من المعاملات البريئة، كم انعلّم غلط.
"""


def _as_ints(y_true, y_pred):
    """يتأكد إن القائمتين بنفس الطول، ويرجّعهما كأعداد صحيحة."""
    t = [int(v) for v in y_true]
    p = [int(v) for v in y_pred]
    if len(t) != len(p):
        raise ValueError(f"طول y_true ({len(t)}) مو نفس طول y_pred ({len(p)})")
    return t, p


def metrics(y_true, y_pred):
    """يرجع مصفوفة الالتباس والمؤشرات الثلاثة (12.1).

    القسمة على صفر ترجع 0 بدل Exception: مجموعة ما فيها تنبيهات معناها
    precision مو معرّف، ونبيه يطبع 0 بدل ما يكسر التقرير كله.
    """
    t, p = _as_ints(y_true, y_pred)
    tp = sum(1 for a, b in zip(t, p) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(t, p) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(t, p) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(t, p) if a == 0 and b == 0)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "n": len(t),
        "scam_total": tp + fn,
        "legit_total": fp + tn,
        "alerted": tp + fp,
    }


def recall_by_group(y_true, y_pred, groups):
    """recall لكل مجموعة — نستعملها لـ recall حسب نوع الاحتيال (12.2).

    groups: قائمة بنفس طول y_true (مثلاً scam_type لكل معاملة).
    المقام هو معاملات الاحتيال من هالنوع فقط (tp + fn) مثل تعريف recall بـ12.1،
    مو كل معاملات النوع: المعاملات البريئة تنحسب بـ n بس.
    """
    t, p = _as_ints(y_true, y_pred)
    names = list(groups)
    if len(names) != len(t):
        raise ValueError(f"طول groups ({len(names)}) مو نفس طول y_true ({len(t)})")

    out = {}
    for name, a, b in zip(names, t, p):
        row = out.setdefault(name, {"tp": 0, "fn": 0, "n": 0})
        row["n"] += 1
        if a == 1:
            row["tp" if b == 1 else "fn"] += 1
    for row in out.values():
        row["scam_total"] = row["tp"] + row["fn"]
        row["recall"] = row["tp"] / row["scam_total"] if row["scam_total"] else 0.0
    return out


def macro_recall(group_recalls):
    """متوسط الـ recall بين المجموعات — رقم واحد يقارن الأنواع ببعض."""
    values = list(group_recalls.values())
    if not values:
        return 0.0
    return sum(r["recall"] for r in values) / len(values)
