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

## 3. طبقة التوجيه باللهجة العراقية — ⚠️ منفذ جزئياً (Partially Implemented)

**المنفذ:**
- `src/coaching/templates.py` — قوالب كاملة باللهجة العراقية (8 أنماط + عامة)، ≤ 60 كلمة
- `src/coaching/llm.py` — استدعاء Gemini (`google-genai`) + تحقق من الناتج + fallback للقالب
- `src/coaching/coach.py` — ينسّق: قالب أولاً، LLM اختياري فوقه
- بوستركتات مكتوبة بالملحق أ من ROADMAP

**الناقص (حسب ROADMAP T2):**
- ❌ `COACH_MODE` بـ `.env` (template | llm | auto) — حالياً `LLM_ENABLED` ثابت بـ config
- ❌ سكربت `try_llm` لتجربة 5 سيناريوهات
- ❌ أعمدة `latency_ms`, `llm_error` بجدول السجل
- ❌ Intake Agent (نص حر) — T6 بعد ما بدأ

---

## 4. خيار المستخدم والتسجيل — ⚠️ منفذ جزئياً (Partially Implemented)

**المنفذ:**
- `POST /api/choice` — يسجّل `user_choice` (continue/cancel) و`choice_at`
- `decision_log` — جدول كامل يحفظ: القرار، الأسباب، رسالة التوعية، الاختيار
- تصدير JSONL/CSV (`GET /api/log/export`)
- واجهة السجل `log.html` بفلاتر
- اختيار "أكمل" على مستلم جديد يضيفه للموثوقين (تخفيف الإنذار القادم)

**الناقص (حسب ROADMAP T2):**
- ❌ `final_status` (pending / completed / cancelled) — حقل غير موجود
- ❌ معالجة `no_response` (المستخدم سكّر النافذة بدون اختيار)

---

## 5. مجموعة الاختبار ومقاييس الأداء — ✅ منفذ بالكامل (Fully Implemented)

**الأدلة:**
- `data/test_sealed/` — **10 مستخدم معزولين، 1,561 معاملة، 56 احتيال** (منفصل عن dev)
- `src/eval/metrics.py` — precision / recall / FPR
- `src/eval/evaluate.py` — يحسب كل المقاييس + baseline للمقارنة + recall حسب نوع الاحتيال
- `docs/eval_results.json` — نتائج dev محفوظة
- قيود الانضباط: `--final` يشتغل مرة وحدة بأمر صريح فقط

**ملاحظة:** التشغيل النهائي على test (T9) لم يُشغَّل بعد — وهذا **مقصود** مو ناقص (بواسطة أمر هبو فقط).

---

## 6. حالات الفشل — ❌ غير منفذ (Not Implemented at All)

**مفقود:**
- ❌ `src/eval/failure_modes.py` (سكريبت السيناريوهات الثابتة FM1–FM6)
- ❌ `docs/failure_modes.md` (التوثيق بالعربي)
- ❌ `docs/evaluation_report.md`
- ❌ ربط الحالات بـ `results.html`

**اللي موجود ويعتبر fallback جزئي:**
- ✅ Fallback للقوالب إذا الـ LLM فشل (يعمل ومجرب بالاختبارات)
- ✅ المدخلات الغريبة ترجع 422 بدل الانهيار

---

## ملخص سريع

| # | البند | الحالة |
|---|-------|--------|
| 1 | البيانات الاصطناعية + الكتالوج | ✅ منفذ بالكامل |
| 2 | قواعد الكشف (بدون LLM) | ✅ منفذ بالكامل |
| 3 | التوجيه باللهجة + LLM | ⚠️ منفذ جزئياً (T2 جزئي، T6 ناقص) |
| 4 | خيار المستخدم + السجل | ⚠️ منفذ جزئياً (final_status ناقص) |
| 5 | الاختبار المعزول + المقاييس | ✅ منفذ بالكامل (التشغيل النهائي T9 معلّق بأمر) |
| 6 | حالات الفشل | ❌ غير منفذ (T7 لم يبدأ) |

**ملفات مفقودة أيضاً:** `README.md`, `.env.example`, `docs/data_review.md`, `docs/user_research.md`
