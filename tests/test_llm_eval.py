"""اختبارات T8: سكربت تقييم الـ LLM — mock وشاتات فقط (صفر إنترنت)."""

import csv

from src import config
from src.coaching import llm
from src.coaching.templates import build_message
from src.detection.rules import load_catalogue
from src.eval import llm_eval


def _assessment(decision="hold", score=95):
    """شكل assessment مبسّط يكفي build_message (قالب) و run_eval."""
    return {
        "score": score,
        "raw_score": score,
        "decision": decision,
        "reasons": [
            {"rule_id": "NEW_RECIPIENT", "points": 20,
             "text_ar": "أول مرة تحوّل لهذا الشخص"}
        ],
        "matched_pattern": None,
        "pattern": None,
        "rules_version": "v1",
    }


def _rows(n_scam=12, n_legit=12):
    rows = []
    for i in range(n_scam):
        rows.append({"tx_id": f"scam_{i:02d}", "user_id": "u1",
                     "is_scam": 1, "assessment": _assessment()})
    for i in range(n_legit):
        rows.append({"tx_id": f"legit_{i:02d}", "user_id": "u2",
                     "is_scam": 0, "assessment": _assessment("allow", 5)})
    return rows


# ----------------------------------------------------------------- الاختيار
def test_select_scenarios_is_balanced_and_deterministic():
    rows = _rows()
    first = llm_eval.select_scenarios(rows)
    second = llm_eval.select_scenarios(rows)

    assert len(first) == 20
    assert sum(r["is_scam"] for r in first) == 10       # 10 احتيال
    assert sum(1 - r["is_scam"] for r in first) == 10    # 10 بريء
    assert [r["tx_id"] for r in first] == [r["tx_id"] for r in second]
    # نفس الـ 20 عند أي عدد أقل من الحد
    assert len(llm_eval.select_scenarios(rows, per_class=3)) == 6


# ----------------------------------------------------------------- بناء الصفوف
def test_build_rows_keeps_labels_out_of_assessment():
    txs = [
        {"tx_id": "t1", "user_id": "u1", "ts": "2026-10-01T14:00:00+03:00",
         "amount_iqd": 100_000, "recipient_id": "r1", "tx_type": "transfer",
         "is_scam": 1, "scam_type": "x", "case_id": "c1"},
        {"tx_id": "t2", "user_id": "u1", "ts": "2026-10-02T14:00:00+03:00",
         "amount_iqd": 90_000, "recipient_id": "r2", "tx_type": "transfer",
         "is_scam": 0},
    ]
    rows = llm_eval.build_rows(txs, load_catalogue())

    assert [r["tx_id"] for r in rows] == ["t1", "t2"]
    assert rows[0]["is_scam"] == 1   # meta يحمل التصنيف (لتوزيع الاختيار)
    for r in rows:                   # بس assessment ما يشوفه أبداً
        assert "is_scam" not in r["assessment"]
        assert "scam_type" not in r["assessment"]
        assert "case_id" not in r["assessment"]


# ----------------------------------------------------------------- الكتابة
def test_run_eval_writes_csv_with_empty_rating_columns(tmp_path):
    scenarios = [
        {"tx_id": "s1", "user_id": "u1", "is_scam": 1, "assessment": _assessment()},
        {"tx_id": "s2", "user_id": "u1", "is_scam": 0,
         "assessment": _assessment("allow", 5)},
        {"tx_id": "s3", "user_id": "u2", "is_scam": 1, "assessment": _assessment()},
        {"tx_id": "s4", "user_id": "u2", "is_scam": 0,
         "assessment": _assessment("allow", 5)},
    ]
    calls = {"n": 0}

    def fake_coach(assessment):
        calls["n"] += 1
        if calls["n"] % 2:  # نصيحة، نصيحة fallback بالتناوب
            return {"message": "صياغة تجريبية باللهجة", "source": "llm"}, 120.0
        return {"message": build_message(assessment), "source": "template"}, 30.0

    out = tmp_path / "llm_evaluation.csv"
    summary = llm_eval.run_eval(scenarios, coach_fn=fake_coach, out_path=out)

    # الأرقام المطلوبة بـ ROADMAP: نجاح + fallback + متوسط وأقصى latency
    assert summary["n"] == 4
    assert summary["llm_ok"] == 2 and summary["fallback"] == 2
    assert summary["ok_rate"] == 0.5 and summary["fallback_rate"] == 0.5
    assert summary["avg_latency_ms"] == 75.0
    assert summary["max_latency_ms"] == 120.0
    assert summary["csv_path"] == str(out)

    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert set(rows[0].keys()) == set(llm_eval.FIELDNAMES)
    # عمودا التقييم فارغين — يملأهما الشخصان لاحقاً
    assert all(r["rating_1_5"] == "" and r["rating_1_5_second"] == "" for r in rows)
    assert [r["llm_status"] for r in rows] == ["ok", "fallback", "ok", "fallback"]
    assert rows[1]["llm_message"] == ""          # fallback: ماكو نص LLM للمقارنة
    assert rows[0]["llm_message"] == "صياغة تجريبية باللهجة"
    # العربي سليم UTF-8 داخل الملف
    assert "صياغة تجريبية" in out.read_text(encoding="utf-8-sig")


def test_run_eval_with_zero_scenarios_is_safe(tmp_path):
    summary = llm_eval.run_eval([], coach_fn=lambda a: ({"source": "template"}, 1.0),
                                out_path=tmp_path / "empty.csv")
    assert summary["n"] == 0 and summary["ok_rate"] == 0.0
    assert summary["avg_latency_ms"] == 0.0


# ----------------------------------------------------------------- main
def test_main_refuses_when_llm_disabled(monkeypatch, tmp_path):
    """بدون مفتاح/تفعيل: يرفض قبل ما يلمس أي بيانات، ويرجع 1."""
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    monkeypatch.setattr(llm, "load_api_key", lambda: None)
    out = tmp_path / "never.csv"
    monkeypatch.setattr(llm_eval, "OUT_PATH", out)
    assert llm_eval.main() == 1
    assert not out.exists()
