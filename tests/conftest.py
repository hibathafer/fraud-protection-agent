"""عزل الاختبارات عن البيئة الحقيقية (قاعدة AGENTS.md: mock حصراً).

عند المطوّر ممكن يكون `.env` فيه `COACH_MODE=llm` ومفتاح Gemini — بدون هذا
السطر صار في خطر استدعاء LLM حقيقي (إنترنت + استهلاك رصيد) داخل pytest.

- نوقف LLM بحمل ملف الاختبارات.
- أي اختبار يريد LLM يفعّله بنفسه بـ monkeypatch (مثل `llm_ready`)،
  وأي تعديل يرجع للوضع الأساسي تلقائياً بعد الاختبار.
"""

from src import config

config.LLM_ENABLED = False
