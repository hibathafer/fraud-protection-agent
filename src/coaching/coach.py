"""ينسّق رسالة التوعية: القالب أولاً دائماً، والـ LLM اختياري فوقه (قسم 8.3).

الترتيب: نبني القالب، وبعدين إذا كان الـ LLM مفعّل نطلب منه صياغة إعادة.
أي فشل (ما في مفتاح / خطأ / مهلة / ناتج مرفوض) يرجع القالب بدون أي خطأ.
الكاش: (النمط + الأسباب + القرار) => رسالة، حتى الديمو يبقى سريع وثابت.
"""

from src.coaching import llm
from src.coaching.templates import build_message

_CACHE = {}

# اسم الرسالة بالواجهة: نخليه قصير حتى ما يطغى على التحذير
MAX_REASONS_IN_PROMPT = 3


def reasons_text(assessment: dict) -> str:
    """الأسباب كنص عربي للمدخل: للرسالة وللـ LLM."""
    reasons = [r for r in (assessment.get("reasons") or []) if r.get("points", 0) > 0]
    return ". ".join(
        r["text_ar"] for r in reasons[:MAX_REASONS_IN_PROMPT] if r.get("text_ar")
    )


def cache_key(assessment: dict, use_llm: bool) -> tuple:
    """مفتاح الكاش: النمط + الأسباب + القرار (+ هل طلبنا LLM)."""
    return (
        assessment.get("matched_pattern"),
        tuple(
            (r.get("rule_id"), r.get("points"))
            for r in (assessment.get("reasons") or [])
            if r.get("points", 0) > 0
        ),
        assessment.get("decision"),
        bool(use_llm),
    )


def clear_cache() -> None:
    """يمسح الكاش (اختبارات والديمو)."""
    _CACHE.clear()


def coach(assessment: dict, use_llm: bool = False, client=None) -> dict:
    """يرجع {"message": ..., "source": "template" | "llm"}.

    client: اختياري ونستعمله بالاختبارات فقط (بدل الاتصال بالنت).
    ما يعدّل assessment: القرار و score ما يتغيرون أبداً.
    """
    key = cache_key(assessment, use_llm)
    cached = _CACHE.get(key)
    if cached:
        return dict(cached)

    message = build_message(assessment)  # القالب جاهز دائماً
    result = {"message": message, "source": "template"}

    if use_llm and llm.enabled():
        rewritten = llm.rewrite(message, reasons_text(assessment), client=client)
        if rewritten:
            result = {"message": rewritten, "source": "llm"}

    _CACHE[key] = dict(result)
    return result
