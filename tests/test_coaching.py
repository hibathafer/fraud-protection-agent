"""اختبارات طبقة التوعية: القوالب باللهجة، وحدود الطول، وفحص ناتج الـ LLM (8 و17).

ما في أي اتصال حقيقي بالنت: الـ LLM دائماً client مزيف.
"""

import copy
from datetime import timedelta

import pytest

from src import config
from src.coaching import llm
from src.coaching.coach import cache_key, clear_cache, coach
from src.coaching.templates import (
    GENERIC_TEMPLATES,
    GENERIC_WARNING_LINE,
    PATTERN_TEMPLATES,
    build_message,
    generic_key_for,
    word_count,
)
from src.detection.engine import assess
from src.detection.features import build_profile, parse_ts
from src.detection.rules import load_catalogue

NOW = "2026-10-20T14:00:00+03:00"
NOW_DT = parse_ts(NOW)
CATALOGUE = load_catalogue()


def has_arabic(text):
    return any("\u0600" <= ch <= "\u06ff" for ch in text)


def at(days_ago=0, hour=None):
    dt = NOW_DT - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0).isoformat() if hour else dt.isoformat()


def hist(n=12, amount=100_000, recipient="r1"):
    return [
        {"ts": at(days_ago=30, hour=14), "amount_iqd": amount,
         "recipient_id": recipient, "tx_type": "transfer"}
        for _ in range(n)
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
    return assess(transaction, build_profile(history, NOW, transaction["recipient_id"], **kw),
                  CATALOGUE)


# ----------------------------------------------------------------- قوالب كل الأنماط
def assessment_for(pattern, decision="warn", extra_reasons=()):
    reasons = [{"rule_id": "SCAM_PATTERN", "points": 35,
                "text_ar": f"الرسالة تطابق نمط معروف: {pattern['name_ar']}"}]
    reasons.extend(extra_reasons)
    return {"score": 35, "decision": decision, "reasons": reasons,
            "matched_pattern": pattern["id"], "pattern": pattern}


def test_every_catalogue_pattern_has_a_template():
    ids = {p["id"] for p in CATALOGUE}
    assert len(ids) == 8
    assert ids <= set(PATTERN_TEMPLATES), "ينقصنا قالب لنمط بالكتالوج"


def test_pattern_template_has_iraqi_tag_and_both_tones():
    for pattern_id, tpl in PATTERN_TEMPLATES.items():
        assert has_arabic(tpl["tag"]), pattern_id
        assert has_arabic(tpl["warn"]) and has_arabic(tpl["hold"]), pattern_id
        assert tpl["warn"] != tpl["hold"], f"النبرة لازم تختلف بنمط {pattern_id}"


def test_every_pattern_message_has_three_parts_and_max_words():
    for pattern in CATALOGUE:
        for decision in ("warn", "hold"):
            message = build_message(assessment_for(pattern, decision))
            assert word_count(message) <= config.COACHING_MAX_WORDS, message
            assert has_arabic(message)
            assert "«" in message and "»" in message          # (2) الجملة المتوقعة
            assert "شو تسوي:" in message                       # (3) شو تسوي
            assert "المريب:" in message                        # (1) المريب من الأسباب
            assert message.index("المريب:") < message.index("غالباً يكول بعدها:")


def test_every_generic_template_has_three_parts_and_max_words():
    for key, tpl in GENERIC_TEMPLATES.items():
        for decision in ("warn", "hold"):
            assessment = {
                "score": 45, "decision": decision, "matched_pattern": None, "pattern": None,
                "reasons": [{"rule_id": r, "points": 20, "text_ar": "سبب مكتوب بالعربي"}
                            for r in tpl["needs"]] or [
                    {"rule_id": "YOUNG_RECIPIENT_ACCOUNT", "points": 15,
                     "text_ar": "حساب المستلم فتح من 2 يوم فقط"}],
            }
            message = build_message(assessment)
            assert word_count(message) <= config.COACHING_MAX_WORDS, (key, message)
            assert has_arabic(message)
            assert "«" in message and "شو تسوي:" in message
            assert "المريب:" in message


def test_generic_templates_cover_the_five_required_reasons():
    assert generic_key_for(["NEW_RECIPIENT", "AMOUNT_HIGH"]) == "NEW_RECIPIENT_HIGH_AMOUNT"
    assert generic_key_for(["RAPID_SEQUENCE"]) == "RAPID_SEQUENCE"
    assert generic_key_for(["CUMULATIVE_NEW_RECIPIENT"]) == "CUMULATIVE_NEW_RECIPIENT"
    assert generic_key_for(["BALANCE_DRAIN"]) == "BALANCE_DRAIN"
    assert generic_key_for(["ODD_HOUR"]) == "ODD_HOUR"
    assert generic_key_for(["AMOUNT_HIGH"]) == "DEFAULT"


def test_warn_tone_is_calmer_than_hold():
    reasons = [
        {"rule_id": "NEW_RECIPIENT", "points": 20, "text_ar": "أول مرة تحوّل لهذا الشخص"},
        {"rule_id": "AMOUNT_HIGH", "points": 25,
         "text_ar": "المبلغ 800,000 أكبر بكثير من عادتك (الحد 300,000)"},
    ]
    base = {"matched_pattern": None, "pattern": None, "reasons": reasons}
    warn = build_message(dict(base, decision="warn"))
    hold = build_message(dict(base, decision="hold"))
    assert "كمّل" in warn
    assert "أنهي" in hold and "أنهي" not in warn
    assert "وقفة ضرورية" in hold and "وقفة ضرورية" not in warn


def test_message_drops_negative_reason_and_keeps_generic_warning():
    assessment = assessment_for(
        CATALOGUE[0], "hold",
        [{"rule_id": "TRUSTED_RECIPIENT", "points": -25, "text_ar": "هالمستلم موثوق"}],
    )
    message = build_message(assessment)
    assert GENERIC_WARNING_LINE in message
    assert "موثوق" not in message


def test_long_reason_list_never_exceeds_max_words():
    reasons = [
        {"rule_id": "SCAM_PATTERN", "points": 35, "text_ar": "الرسالة تطابق نمط معروف: موظف مزيف"},
        {"rule_id": "NEW_RECIPIENT", "points": 20, "text_ar": "أول مرة تحوّل لهذا الشخص"},
        {"rule_id": "AMOUNT_HIGH", "points": 25,
         "text_ar": "المبلغ 800,000 أكبر بكثير من عادتك (الحد 300,000)"},
        {"rule_id": "ODD_HOUR", "points": 10, "text_ar": "ساعة غريبة: 3:00 بعد منتصف الليل"},
    ]
    message = build_message({"score": 100, "decision": "hold", "reasons": reasons,
                             "matched_pattern": None, "pattern": None})
    assert word_count(message) <= config.COACHING_MAX_WORDS
    assert has_arabic(message)


def test_real_assessment_produces_iraqi_message():
    result = run(tx(recipient_id="r_new", recipient_age_days=2, amount_iqd=800_000,
                    balance_before_iqd=4_000_000,
                    context_message="موظف الدعم يطلب رمز تحقق منك"))
    result["pattern"] = next(p for p in CATALOGUE if p["id"] == result["matched_pattern"])
    message = build_message(result)
    assert result["matched_pattern"] == "otp_fake_agent"
    assert has_arabic(message)
    assert word_count(message) <= config.COACHING_MAX_WORDS
    assert "استعجل" in message  # من typical_next_line_ar بالكتالوج
    assert "رمز التحقق" in message  # من advice_ar بالكتالوج


# ----------------------------------------------------------------- عميل LLM مزيف
class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """عميل مزيف: ما يتصل بالنت، ويسجّل عدد الاستدعاءات."""

    def __init__(self, text="", exc=None):
        self.text = text
        self.exc = exc
        self.calls = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.exc:
            raise self.exc
        return FakeResponse(self.text)


VALID_REWRITE = "هاي أول مرة تحوّل لهذا الشخص، والمبلغ كبير على عادة. لا تعطي الرمز لأي أحد."


@pytest.fixture
def llm_ready(monkeypatch):
    """يخلي الـ LLM مفعّل + مفتاح موجود، بدون مفتاح حقيقي."""
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: "test-key")
    clear_cache()
    yield
    clear_cache()


def otp_assessment(decision="warn"):
    pattern = next(p for p in CATALOGUE if p["id"] == "otp_fake_agent")
    return assessment_for(pattern, decision,
                          [{"rule_id": "NEW_RECIPIENT", "points": 20,
                            "text_ar": "أول مرة تحوّل لهذا شخص"}])


# ----------------------------------------------------------------- coach: القالب أولاً
def test_coach_returns_template_by_default():
    clear_cache()
    result = coach(otp_assessment())
    assert result["source"] == "template"
    assert word_count(result["message"]) <= config.COACHING_MAX_WORDS
    assert has_arabic(result["message"])


def test_coach_uses_llm_when_it_works(llm_ready):
    client = FakeClient(VALID_REWRITE)
    result = coach(otp_assessment(), use_llm=True, client=client)
    assert result == {"message": VALID_REWRITE, "source": "llm"}
    assert client.calls == 1


def test_fallback_when_no_api_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: None)
    client = FakeClient(VALID_REWRITE)
    clear_cache()
    result = coach(otp_assessment(), use_llm=True, client=client)
    assert result["source"] == "template"
    assert client.calls == 0  # ما حاولنا نتصل


def test_fallback_when_llm_is_disabled(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    monkeypatch.setattr(llm, "load_api_key", lambda: "test-key")
    client = FakeClient(VALID_REWRITE)
    clear_cache()
    assert coach(otp_assessment(), use_llm=True, client=client)["source"] == "template"
    assert client.calls == 0


def test_fallback_on_error(llm_ready):
    client = FakeClient(exc=RuntimeError("503 من المزود"))
    result = coach(otp_assessment(), use_llm=True, client=client)
    assert result["source"] == "template"
    assert word_count(result["message"]) <= config.COACHING_MAX_WORDS


def test_fallback_on_timeout(llm_ready):
    client = FakeClient(exc=TimeoutError("تجاوزت المهلة 4 ثواني"))
    result = coach(otp_assessment("hold"), use_llm=True, client=client)
    assert result["source"] == "template"
    assert has_arabic(result["message"])
    assert word_count(result["message"]) <= config.COACHING_MAX_WORDS


def test_fallback_on_rejected_output(llm_ready):
    hallucinated = "حسابك مخترق! حوّل 5,000,000 instantly إلى https://bank-iraq.example.com"
    result = coach(otp_assessment(), use_llm=True, client=FakeClient(hallucinated))
    assert result["source"] == "template"
    assert "example.com" not in result["message"]


def test_cache_reuses_the_same_message(llm_ready):
    client = FakeClient(VALID_REWRITE)
    first = coach(otp_assessment(), use_llm=True, client=client)
    second = coach(otp_assessment(), use_llm=True, client=FakeClient(VALID_REWRITE))
    assert first == second
    assert client.calls == 1  # المرة الثانية ما عدنا نتصل
    assert first["message"] == VALID_REWRITE


def test_cache_key_separates_patterns_reasons_and_decision():
    a = otp_assessment("warn")
    b = otp_assessment("hold")
    c = assessment_for(CATALOGUE[1], "warn")
    assert cache_key(a, False) != cache_key(b, False)
    assert cache_key(a, False) != cache_key(c, False)
    assert cache_key(a, False) != cache_key(a, True)


def test_coach_never_changes_score_or_decision(llm_ready):
    result = run(tx(recipient_id="r_new", recipient_age_days=1, amount_iqd=9_000_000,
                    balance_before_iqd=10_000_000, ts=at(hour=3),
                    context_message="الحساب موقوف، حوّل لحساب آمن حتى نكمل الإجراء"))
    before = copy.deepcopy(result)
    coach(result, use_llm=True, client=FakeClient(VALID_REWRITE))
    assert result == before
    assert result["decision"] == "hold" and result["score"] == before["score"]


# ----------------------------------------------------------------- فحص ناتج الـ LLM
def test_validate_accepts_a_plain_iraqi_rewrite():
    source = build_message(assessment_for(CATALOGUE[0]))
    assert llm.validate(VALID_REWRITE, source) is True


def test_validate_rejects_empty_and_non_arabic():
    source = build_message(assessment_for(CATALOGUE[0]))
    assert llm.validate("", source) is False
    assert llm.validate("   ", source) is False
    assert llm.validate("This is a plain english reply with no warning", source) is False


def test_validate_rejects_new_number():
    source = "المبلغ 800,000 أكبر من عادتك. لا تدفع شي."
    assert llm.validate("حوّل المبلغ 999,000 بعدين", source) is False
    assert llm.validate("حوّل المبلغ 800,000 بعدين", source) is True
    assert llm.validate("حوّل المبلغ ٨٠٠,٠٠٠ بعدين", source) is True  # أرقام عربية هندية


def test_validate_rejects_new_link():
    source = "لا تعطي الرمز لأي أحد."
    assert llm.validate("راجع https://iraq-bank.example.com للتفاصيل", source) is False
    assert llm.validate("راسلنا على support@iraqbank.com", source) is False
    assert llm.validate("لا تعطي الرمز لأي أحد.", source) is True


def test_validate_rejects_too_long():
    source = "رسالة قصيرة"
    assert llm.validate(" ".join(["تحذير"] * 80), source) is False


def test_rewrite_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm, "load_api_key", lambda: None)
    assert llm.rewrite("قالب", "أسباب") is None


def test_prompt_hides_score_and_decision():
    prompt = llm.build_prompt("القالب باللهجة", "أول مرة تحوّل لهذا الشخص")
    assert "القالب باللهجة" in prompt and "أول مرة تحوّل" in prompt
    assert "score" not in prompt.lower() and "hold" not in prompt.lower()
    assert "warn" not in prompt.lower()
