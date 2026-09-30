"""تقييم نظام الكشف على dev مع baselines وتقرير مطبوع (12.1 و12.2 و12.3).

التشغيل:
    python -m src.eval.evaluate            # dev فقط (الوضع العادي)
    python -m src.eval.evaluate --final    # الاختبار المعزول، مرة وحدة بس (12.4)

قاعدة الانضباط (12.4): الضبط على dev فقط. data/test_sealed/ ما ينقرأ إلا
مع --final، وكل تشغيل نهائي يتسجل تلقائياً بـ docs/test_runs.log.
"""

import argparse
import sys
import time
from datetime import datetime

from src.config import AMOUNT_HIGH_FALLBACK, ROOT, RULES_VERSION
from src.db import get_connection, load_csvs
from src.detection.engine import assess
from src.detection.features import build_profile
from src.detection.rules import load_catalogue
from src.eval.metrics import macro_recall, metrics, recall_by_group

# أهداف ذاتية من 12.3 — مو وعود، والطباعة تقول إذا تحققت أو لا
TARGET_RECALL = 0.80
TARGET_FPR = 0.05
TARGET_PRECISION = 0.50

LOG_PATH = ROOT / "docs" / "test_runs.log"


def load_split(split):
    """يحمّل بيانات السبلت من القاعدة ويرجّع (قائمة dicts مرتبة، عدد المستخدمين).

    نستعمل db.load_csvs لأنها هي اللي تقرر أي ملف ينقرأ (dev من data/synthetic،
    test من data/test_sealed)، وما نكرّر قاعدة الفصل عندنا.
    """
    load_csvs(split=split)
    conn = get_connection()
    try:
        users = conn.execute("SELECT COUNT(*) FROM users WHERE split = ?", (split,)).fetchone()[0]
        rows = conn.execute(
            "SELECT t.* FROM transactions t JOIN users u ON u.user_id = t.user_id "
            "WHERE u.split = ? ORDER BY t.user_id, t.ts",
            (split,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows], users


def run_engine(txs, catalogue):
    """يشغّل المحرك على كل معاملة ويعيد نتائجه بالترتيب نفسه.

    لكل معاملة نبني الـ profile من معاملات المستخدم السابقة لها فقط (7.1)،
    فما فيه تسريب مستقبلي.
    """
    by_user = {}
    for tx in txs:
        by_user.setdefault(tx["user_id"], []).append(tx)

    results = []
    for user_id in sorted(by_user):
        history = []
        for tx in sorted(by_user[user_id], key=lambda r: r["ts"]):
            profile = build_profile(history, tx["ts"], tx.get("recipient_id"), [])
            out = assess(tx, profile, catalogue)
            results.append(
                {
                    "tx_id": tx["tx_id"],
                    "ts": tx["ts"],
                    "user_id": user_id,
                    "amount_iqd": int(tx["amount_iqd"]),
                    "tx_type": tx["tx_type"],
                    "is_scam": int(tx["is_scam"] or 0),
                    "scam_type": tx["scam_type"],
                    "score": out["score"],
                    "decision": out["decision"],
                    "reasons": out["reasons"],
                    "is_new_recipient": profile["recipient"]["count"] == 0,
                }
            )
            history.append(tx)
    return results


def build_predictions(results):
    """y_true وy_pred لكل نظام نقارن بيه (12.2)."""
    y_true = [r["is_scam"] for r in results]
    return {
        "any_alert": [1 if r["decision"] in ("warn", "hold") else 0 for r in results],
        "hold_only": [1 if r["decision"] == "hold" else 0 for r in results],
        # baseline ساذج 1: أول تحويل لأي مستلم (نفس signal اللي قاعدة NEW_RECIPIENT تستعمله)
        "baseline_new_recipient": [
            1 if r["is_new_recipient"] and r["tx_type"] == "transfer" else 0 for r in results
        ],
        # baseline ساذج 2: مبلغ كبير، عتبة ثابتة بدل مقارنة بعادات المستخدم
        "baseline_large_amount": [1 if r["amount_iqd"] > AMOUNT_HIGH_FALLBACK else 0 for r in results],
    }, y_true


def fmt_pct(v):
    return f"{v * 100:5.1f}%"


def render_table(headers, rows):
    """جدول ASCII بعرض ثابت، الأعمدة أرقام من اليمين."""
    cells = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in cells:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(c))
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [sep, "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |", sep]
    for row in cells:
        out.append("| " + " | ".join(c.rjust(w) for c, w in zip(row, widths)) + " |")
    out.append(sep)
    return "\n".join(out)


def report(results, y_true, preds, split, elapsed):
    scam_total = sum(y_true)
    print("=" * 78)
    print(f" تقييم كشف الاحتيال — split={split} — rules_version={RULES_VERSION}")
    print("=" * 78)
    print(
        f"البيانات: {len(results)} معاملة | {scam_total} احتيال "
        f"({scam_total / len(results) * 100:.1f}%) | المدة {elapsed:.1f}s"
    )
    print(
        f"كل الحسابات هنا على y_pred = 1 للقرار warn أو hold (12.1). "
        f"الاحتيال نادر ({scam_total / len(results) * 100:.1f}% من المعاملات)، "
        "لذلك precision تنزل بسهولة — طبيعي مو خلل."
    )

    print("\n[1] توزيع القرارات")
    counts = {}
    for r in results:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(
        "  allow={allow}  warn={warn}  hold={hold}".format(
            allow=counts.get("allow", 0), warn=counts.get("warn", 0), hold=counts.get("hold", 0)
        )
    )

    print("\n[2] مصفوفة الالتباس — \"أي تنبيه\" (warn أو hold)")
    m_any = metrics(y_true, preds["any_alert"])
    print(f"  actual=1 (احتيال):  predicted=1 -> TP={m_any['tp']:>5}   predicted=0 -> FN={m_any['fn']:>5}")
    print(f"  actual=0 (بريء):    predicted=1 -> FP={m_any['fp']:>5}   predicted=0 -> TN={m_any['tn']:>5}")

    print("\n[3] المؤشرات: النظام مقابل الـ baselines (12.2)")
    rows = []
    all_m = {}
    for name in ("any_alert", "hold_only", "baseline_new_recipient", "baseline_large_amount"):
        m = metrics(y_true, preds[name])
        all_m[name] = m
        rows.append(
            [name, m["tp"], m["fp"], m["fn"], m["tn"], fmt_pct(m["precision"]),
             fmt_pct(m["recall"]), fmt_pct(m["fpr"])]
        )
    print(render_table(["system", "TP", "FP", "FN", "TN", "prec", "recall", "FPR"], rows))
    print("  any_alert = القرار warn أو hold | hold_only = القرار hold بس")
    print("  baseline_new_recipient = ينبّه على أول تحويل لأي مستلم (تحويلات بس)")
    print(f"  baseline_large_amount = ينبّه على أي مبلغ أكبر من {AMOUNT_HIGH_FALLBACK:,} (عتبة ثابتة)")

    print("\n[4] أهداف 12.3 على \"أي تنبيه\" (أهداف ذاتية، مو وعود)")
    for label, value, target, higher_is_better in (
        ("recall", m_any["recall"], TARGET_RECALL, True),
        ("FPR", m_any["fpr"], TARGET_FPR, False),
        ("precision", m_any["precision"], TARGET_PRECISION, True),
    ):
        ok = value >= target if higher_is_better else value <= target
        goal = f">= {target * 100:.0f}%" if higher_is_better else f"<= {target * 100:.0f}%"
        print(f"  {label:<10} {fmt_pct(value)}  (الهدف {goal})   {'تحقق' if ok else 'ما تحقق'}")

    print("\n[5] recall حسب نوع الاحتيال — النظام (أي تنبيه)")
    per_type = recall_by_group(y_true, preds["any_alert"], [r["scam_type"] or "—" for r in results])
    scam_types = {r["scam_type"] for r in results if r["is_scam"]}
    # الترتيب بالرقم مو بالنص المطبوع، وإلا "10.0%" ترتح قبل " 9.0%"
    type_rows = sorted((per_type[name]["recall"], name, per_type[name]) for name in scam_types)
    print(
        render_table(
            ["scam_type", "TP", "FN", "scam", "recall"],
            [[name, row["tp"], row["fn"], row["scam_total"], fmt_pct(recall)] for recall, name, row in type_rows],
        )
    )
    print(f"  macro recall (متوسط بين الأنواع) = {fmt_pct(macro_recall(per_type))}")

    print("\n[6] hold فقط حسب نوع الاحتيال")
    hold_types = recall_by_group(y_true, preds["hold_only"], [r["scam_type"] or "—" for r in results])
    hold_rows = sorted((hold_types[name]["recall"], name, hold_types[name]) for name in scam_types)
    print(
        render_table(
            ["scam_type", "TP", "FN", "recall(hold)"],
            [[name, row["tp"], row["fn"], fmt_pct(recall)] for recall, name, row in hold_rows],
        )
    )

    return all_m, m_any, per_type


def show_cases(results, limit=5):
    """قائمة FN وFP مقروءة (قائمة التحقق الأسبوع 2) — أهمها يبيّن شي نصلحه."""
    missed = [r for r in results if r["is_scam"] == 1 and r["decision"] == "allow"]
    false_alarm = [r for r in results if r["is_scam"] == 0 and r["decision"] != "allow"]
    print(f"\n[7] FN (احتيال فات): {len(missed)} | FP (إنذار كاذب): {len(false_alarm)}")
    print(f"  أمثلة FN (أول {min(limit, len(missed))}):")
    for r in missed[:limit]:
        print(f"    {r['tx_id']}  {r['scam_type'] or '—':<22} score={r['score']:>3}  amount={r['amount_iqd']:,}")
    print(f"  أمثلة FP (أول {min(limit, len(false_alarm))}):")
    for r in false_alarm[:limit]:
        top = r["reasons"][0]["text_ar"] if r["reasons"] else "بلا سبب"
        print(f"    {r['tx_id']}  score={r['score']:>3}  amount={r['amount_iqd']:,}  {top}")


def log_final_run(split, all_m, m_any, per_type):
    """كل تشغيل نهائي يتسجل (12.4): التاريخ + rules_version + النتائج."""
    line = (
        f"{datetime.now().isoformat(timespec='seconds')}  split={split}  "
        f"rules_version={RULES_VERSION}  "
        f"any_alert: P={m_any['precision']:.3f} R={m_any['recall']:.3f} FPR={m_any['fpr']:.3f}  "
        f"TP={m_any['tp']} FP={m_any['fp']} FN={m_any['fn']} TN={m_any['tn']}  "
        f"hold_only: P={all_m['hold_only']['precision']:.3f} R={all_m['hold_only']['recall']:.3f} "
        f"FPR={all_m['hold_only']['fpr']:.3f}  "
        f"macro_recall={macro_recall(per_type):.3f}"
    )
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"\nسُجّل التشغيل في {LOG_PATH}")


def main(split="dev"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    started = time.perf_counter()
    txs, users = load_split(split)
    catalogue = load_catalogue()
    results = run_engine(txs, catalogue)
    preds, y_true = build_predictions(results)
    elapsed = time.perf_counter() - started

    print(f"مستخدمين: {users} | معاملات: {len(results)} | catalogue: "
          f"{len(catalogue)} نمط")
    all_m, m_any, per_type = report(results, y_true, preds, split, elapsed)
    show_cases(results)

    if split == "test":
        log_final_run(split, all_m, m_any, per_type)
    else:
        print("\nهذي نتائج dev فقط. الاختبار المعزول (data/test_sealed/) ما انمس "
              "— والنظام ما يتغير بعد ما تشوفين نتايجه.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="تقييم كشف الاحتيال (قسم 12)")
    parser.add_argument("--final", action="store_true",
                        help="الاختبار المعزول: يقرأ data/test_sealed/ ويسجل بـ docs/test_runs.log (مرة وحدة بس)")
    args = parser.parse_args()
    sys.exit(main("test" if args.final else "dev"))
