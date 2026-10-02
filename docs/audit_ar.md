# تدقيق المشروع — الإجابة عن 6 أسئلة

فحصت الملفات والمجلدات فعلياً قبل كتابة هذا الجواب.

---

## 1. البيانات الاصطناعية والمستخدمين — ✅ منفذ بالكامل (Fully Implemented)

**الأدلة:**
- `src/generator/generate_data.py` — سكريبت التوليد (seed=42)
- `data/synthetic/users.csv` — **30 مستخدم** (20 dev + 10 test)
- `data/synthetic/transactions.csv` — **3,095 معاملة** منها **152 حالة احتيال**
- `data/scam_catalogue.json` — **8 أنماط احتيال** عراقية مع كلمات مفتاحية ونصوص نصائح

**ملاحظة:** نصوص LLM (T3) لم تُولَّد بعد، فالنصوص الحالية يدوية/مولّدة سابقاً.

---

## 2. طبقة الكشف بالقواعد الثابتة — ✅ منفذ بالكامل (Fully Implemented)

**الأدلة:**
- `src/detection/rules.py` — 9 قواعد (أول تحويل، مبلغ مرتفع، وقت غريب، تتابع سريع، تطابق كتالوج...)
- `src/detection/features.py` — إحصاءات من معاملات الماضي فقط (مثبت باختبار عدم التسريب)
- `src/detection/engine.py` — `score → allow/warn/hold` بدون أي LLM
- اختبارات تثبت: LLM ما يغيّر القرار أبداً
- كل سبب مكتوب بالعربي (`Reason.text_ar`)

---

## 3. طبقة التوجيه باللهجة العراقية — ✅ منفذ بالكامل (Fully Implemented)

**المنفذ:**
- `src/coaching/templates.py` — قوالب كاملة باللهجة العراقية (8 أنماط + عامة)، ≤ 60 كلمة
- `src/coaching/llm.py` — استدعاء Gemini (`google-genai`) + تحقق من الناتج + fallback للقالب
- `src/coaching/coach.py` — ينسّق: قالب أولاً، LLM اختياري فوقه
- بوستركتات مكتوبة بالملحق أ من ROADMAP

**الناقص (حسب ROADMAP T2):**
- ✅ `COACH_MODE` بـ `.env` (template | llm | auto) — نُفّذ بـ T10 بـ `src/config.py` (سابقاً كان `LLM_ENABLED` ثابت)
- ✅ بديل سكربت `try_llm`: `python -m src.demo_check` (5 سيناريوهات + سلامات الموديل) و`python -m src.eval.llm_eval` (تقييم القالب مقابل LLM)
- ✅ Intake Agent (نص حر) — نُفّذ بـ T6 (`src/agents/intake.py`)
- ❌ أعمدة `latency_ms`, `llm_error` بجدول السجل — غير موجودة (القياس بـ `demo_check` وقت التشغيل بس؛ تحسين اختياري مو مطلوب بالخارطة)

---

## 4. خيار المستخدم والتسجيل — ⚠️ منفذ جزئياً (Partially Implemented)

**المنفذ:**
- `POST /api/choice` — يسجّل `user_choice` (continue/cancel) و`choice_at`
- `decision_log` — جدول كامل يحفظ: القرار، الأسباب، رسالة التوعية، الاختيار
- تصدير JSONL/CSV (`GET /api/log/export`)
- واجهة السجل `log.html` بفلاتر
- اختيار "أكمل" على مستلم جديد يضيفه للموثوقين (تخفيف الإنذار القادم)

**الناقص (حسب ROADMAP T2):**
- ✅ `final_status` (pending / completed / cancelled) — نُفّذ بـ T5b مع `receipt_json` (إيصال ZC...)
- ❌ معالجة `no_response` (المستخدم سكّر النافذة بدون اختيار) — القيمة تُقبل وتُسجَّل، بس ما فيه معالجة تلقائية للإغلاق الصامت

---

## 5. مجموعة الاختبار ومقاييس الأداء — ✅ منفذ بالكامل (Fully Implemented)

**الأدلة:**
- `data/test_sealed/` — **10 مستخدم معزولين، 1,561 معاملة، 56 احتيال** (منفصل عن dev)
- `src/eval/metrics.py` — precision / recall / FPR
- `src/eval/evaluate.py` — يحسب كل المقاييس + baseline للمقارنة + recall حسب نوع الاحتيال
- `docs/eval_results.json` — نتائج dev محفوظة
- قيود الانضباط: `--final` يشتغل مرة وحدة بأمر صريح فقط

**ملاحظة:** التشغيل النهائي على test (T9) **نُفّذ 2026-10-01 بأمر هبو** — النتائج بـ `docs/evaluation_report.md` (FPR 3.2%، hold precision 91.3%).

---

## 6. حالات الفشل — ✅ منفذ بالكامل (Fully Implemented)

**الأدلة:**
- ✅ `src/eval/failure_modes.py` (سكريبت السيناريوهات الثابتة FM1–FM6)
- ✅ `docs/failure_modes.md` (التوثيق بالعربي — 6 حالات مع النتائج الفعلية)
- ✅ `docs/evaluation_report.md` (نتيجة T9 المعزولة)
- ✅ ربط الحالات بـ `results.html` (`loadFailureModes()` عبر `GET /api/failure_modes`)

**ضمانات جانبية:**
- ✅ Fallback للقوالب إذا الـ LLM فشل (يعمل ومجرب بالاختبارات)
- ✅ المدخلات الغريبة ترجع 422 بدل الانهيار

---

## ملخص سريع

| # | البند | الحالة |
|---|-------|--------|
| 1 | البيانات الاصطناعية + الكتالوج | ✅ منفذ بالكامل |
| 2 | قواعد الكشف (بدون LLM) | ✅ منفذ بالكامل |
| 3 | التوجيه باللهجة + LLM | ✅ منفذ بالكامل (T2 + T6: `COACH_MODE` template/llm/auto + Intake + fallback مختبر) |
| 4 | خيار المستخدم + السجل | ⚠️ منفذ جزئياً (final_status ✅ T5b مع إيصال، ناقص معالجة `no_response` تلقائية) |
| 5 | الاختبار المعزول + المقاييس | ✅ منفذ بالكامل (T9 نُفّذ 2026-10-01: FPR 3.2%، hold precision 91.3%) |
| 6 | حالات الفشل | ✅ منفذ بالكامل (T7: سكربت FM1–FM6 + `docs/failure_modes.md` — 6 حالات) |

**الملفات الأربعة المذكورة موجودة الآن** (`README.md`, `.env.example`, `docs/data_review.md`, `docs/user_research.md`) — الباقي بانتظارك: محتوى `user_research.md` (مقابلاتك) + المرور اليدوي بـ `data_review.md` + ✋ بـ `DISCLOSURE.md`.
