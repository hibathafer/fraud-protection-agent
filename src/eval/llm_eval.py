"""T8: تقييم الـ LLM على 20 سيناريو من dev — تشغيل يدوي بمفتاح حقيقي.

التشغيل (يدوي — يستهلك رصيد Gemini بسيط):
    python -m src.eval.llm_eval

قبل التشغيل:
    - LLM_ENABLED = True بـ src/config.py
    - GEMINI_API_KEY موجود بـ .env

الناتج:
    docs/llm_evaluation.csv  — لكل سيناريو: القالب مقابل صياغة الـ LLM +
    نسبة نجاح الفحص الشكلي + fallback + latency، وعمودا تقييم فارغين
    (rating_1_5 و rating_1_5_second) يملأهما شخصان على الأقل بعدين.

سؤال التقييم للملأين (من ROADMAP T8):
    "هل تشبه كلام شخص من العراق أم إشعار بنك مترجم؟" (1-5)

الاختيار حاسم (10 احتيال + 10 بريء من dev، بالترتيب) => نفس الـ 20 كل مرة.
الاختبارات تحقن coach_fn وشاتات وهمية — هالسكربت ما ينادى منها أبداً.
"""

import csv
import sys
import time

from src.coaching import llm
from src.coaching.coach import clear_cache, coach
from src.coaching.templates import build_message
from src.config import ROOT, RULES_VERSION
from src.detection.engine import assess
from src.detection.features import build_profile
from src.detection.rules import load_catalogue
from src.eval.evaluate import load_split

OUT_PATH = ROOT / "docs" / "llm_evaluation.csv"
N_PER_CLASS = 10  # 10 احتيال + 10 بريء = 20 سيناريو

FIELDNAMES = [
    "scenario_id", "user_id", "is_scam", "decision", "score", "pattern_id",
    "template_message", "llm_message", "llm_status", "latency_ms",
    "rating_1_5", "rating_1_5_second", "notes",
]


def build_rows(txs, catalogue):
    """يقيّم كل معاملة dev بنفس منطق evaluate (بلا تسريب: الماضي فقط).

    الإطار (meta) يحمل is_scam للاختيار والتقرير — assessment ما يشوفه أبداً.
    """
    by_user = {}
    for tx in txs:
        by_user.setdefault(tx["user_id"], []).append(tx)

    rows = []
    for user_id in sorted(by_user):
        history = []
        for tx in sorted(by_user[user_id], key=lambda r: r["ts"]):
            profile = build_profile(history, tx["ts"], tx.get("recipient_id"), [])
            assessment = assess(tx, profile, catalogue)
            rows.append({
                "tx_id": tx["tx_id"],
                "user_id": user_id,
                "is_scam": int(tx.get("is_scam") or 0),  # meta فقط — مو مدخل للمحرك
                "assessment": assessment,
            })
            history.append(tx)
    return rows


def select_scenarios(rows, per_class=N_PER_CLASS):
    """أول 10 احتيال + أول 10 بريء بالترتيب — حاسم وقابل للتكرار."""
    scam = [r for r in rows if r["is_scam"] == 1]
    legit = [r for r in rows if r["is_scam"] == 0]
    return scam[:per_class] + legit[:per_class]


def real_coach(assessment):
    """استدعاء حقيقي: (نتيجة الكوالتش، زمن الاستجابة بـ ms)."""
    clear_cache()  # حتى ما يخدعنا الكاش بزمن صفر
    started = time.perf_counter()
    result = coach(assessment, use_llm=True)
    return result, round((time.perf_counter() - started) * 1000, 1)


def run_eval(scenarios, coach_fn=real_coach, out_path=None):
    """يشغّل التقييم على السيناريوهات ويكتب CSV، ويرجع ملخص الأرقام.

    coach_fn قابل للحقن (الاختبارات تستعمل وهمي — صفر إنترنت).
    """
    out_path = out_path or OUT_PATH
    out_rows = []
    ok = fallback = 0
    latencies = []

    for scenario in scenarios:
        a = scenario["assessment"]
        template_message = build_message(a)  # القالب: نص ثابت يُبنى من assessment
        result, latency_ms = coach_fn(a)
        status = "ok" if result.get("source") == "llm" else "fallback"
        if status == "ok":
            ok += 1
            llm_message = result["message"]
        else:
            fallback += 1
            llm_message = ""  # الـ LLM ما عطى نص صالحاً => المقارنة مع القالب فاضية
        latencies.append(latency_ms)

        out_rows.append({
            "scenario_id": scenario["tx_id"],
            "user_id": scenario["user_id"],
            "is_scam": scenario["is_scam"],
            "decision": a["decision"],
            "score": a["score"],
            "pattern_id": a.get("matched_pattern") or "",
            "template_message": template_message,
            "llm_message": llm_message,
            "llm_status": status,
            "latency_ms": latency_ms,
            "rating_1_5": "",              # تُملأ يدوياً (المُقيِّم الأول)
            "rating_1_5_second": "",       # تُملأ يدوياً (المُقيِّم الثاني)
            "notes": "",
        })

    n = len(out_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig حتى تنفتح بالعربي سليمة بـ Excel
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(out_rows)

    return {
        "n": n,
        "llm_ok": ok,
        "fallback": fallback,
        "ok_rate": (ok / n) if n else 0.0,
        "fallback_rate": (fallback / n) if n else 0.0,
        "avg_latency_ms": round(sum(latencies) / n, 1) if n else 0.0,
        "max_latency_ms": max(latencies) if n else 0.0,
        "csv_path": str(out_path),
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    # فحص قبل أي شي حتى ما نلمس قاعدة البيانات بدون فايدة
    if not llm.enabled():
        print("FAIL llm_enabled: set LLM_ENABLED=True in src/config.py "
              "and GEMINI_API_KEY in .env")
        return 1
    print("PASS llm_enabled: key found")

    txs, users = load_split("dev")
    catalogue = load_catalogue()
    rows = build_rows(txs, catalogue)
    scenarios = select_scenarios(rows)
    print(f"PASS selection: {len(scenarios)} scenarios "
          f"({N_PER_CLASS} scam + {N_PER_CLASS} legit) from dev "
          f"({len(txs)} tx, {users} users), rules_version={RULES_VERSION}")

    summary = run_eval(scenarios)

    # الأرقام المطلوبة بـ ROADMAP T8: نجاح الفحص، fallback، متوسط وأقصى latency
    ok_pass = summary["llm_ok"] > 0
    print(f"{'PASS' if ok_pass else 'FAIL'} llm_check: {summary['llm_ok']}/{summary['n']} "
          f"({summary['ok_rate']:.0%}) accepted by validators")
    print(f"INFO fallback: {summary['fallback']}/{summary['n']} "
          f"({summary['fallback_rate']:.0%}) fell back to template")
    print(f"INFO latency_ms: avg={summary['avg_latency_ms']} "
          f"max={summary['max_latency_ms']}")
    print(f"PASS csv: {summary['csv_path']}")
    print("NEXT: fill rating_1_5 and rating_1_5_second with TWO Iraqi raters "
          "(question: هل تشبه كلام شخص من العراق أم إشعار بنك مترجم؟), "
          "then record results in docs/llm_evaluation.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
