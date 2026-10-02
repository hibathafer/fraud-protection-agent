# سجل التقدم

## المهام

| # | المهمة | الحالة | ملاحظات |
|---|--------|--------|---------|
| T0 | مواءمة الوثائق | ✅ مكتمل | PLAN.md + ROADMAP.md + AGENTS.md |
| T1 | رسائل التوعية + التحقق من المدخلات | ✅ مكتمل | قوالب باللهجة + تحقق Pydantic |
| T2 | ربط Gemini (Coach Agent) | ✅ مكتمل | llm_client + validators + fallback |
| T3 | توليد البيانات بالـ LLM (هجين) | ✅ مكتمل | 30 مستخدم، dev/test مفصولين |
| T4 | مراجعة التقييم وضبط القواعد | ✅ مكتمل | rules_version=v1، baseline |
| T5 | الواجهة (web/) | ✅ مكتمل | index + log + results + demo scenarios |
| T5b | تكامل محفظة Zain Cash (بطلب هبو) | ✅ مكتمل | اعتراض التحويل + إيصال + فترة تهدئة + بستايل المحفظة |
| T6 | Intake Agent (نص حر) | ✅ مكتمل | `src/agents/intake.py` + `/api/scenario_text` + صندوق نص حر بالواجهة |
| T7 | حالات الفشل الموثقة | ✅ مكتمل | `src/eval/failure_modes.py` + `docs/failure_modes.md` (6 حالات، النتائج الفعلية) |
| T8 | أمان وتقييم الـ LLM | ✅ مكتمل | `test_llm_safety.py` (12) + `docs/privacy_notes.md` + `llm_eval.py` + `docs/llm_evaluation.md` (بانتظار تشغيل يدوي بالمفتاح) |
| T9 | الاختبار النهائي المعزول | ✅ مكتمل | `--final` مرة وحدة (2026-10-01) + `docs/evaluation_report.md` + سطر بـ `docs/test_runs.log` — القواعد مجمّدة بعدها |
| T10 | حزمة الديمو والتسليم | ✅ مكتمل | 6 سيناريوهات + `SCRIPT.md` + `QA.md` + `python -m src.demo_check` (6/6 PASS) + `DISCLOSURE.md` + `README.md` + تبديل `COACH_MODE` |
| T11 | Dialogue Agent (اختياري) | ✅ مكتمل | `src/agents/dialogue.py` + `/api/chat` (حد 5 رسائل) + `chat_turns` + مربع حوار بالنافذة + اختبار صريح: لا يغيّر `decision` |
| T12 | وضع التدريب (اختياري) | ✅ مكتمل | `src/agents/training.py` + `/api/training/start`+`/answer` + صندوق تدريب معلن + تقييم بايثون باللهجة + صفر لمسة للقاعدة |

## الوحدات

| الوحدة | الحالة | ملاحظات |
|---------|--------|---------|
| `src/detection/` | ✅ مكتمل | features + rules + engine |
| `src/coaching/` | ✅ مكتمل | templates + coach + llm |
| `src/api/` | ✅ مكتمل | 16 endpoints (15 نقطة + فهرس `/api`) + web mount |
| `src/eval/` | ✅ مكتمل | metrics + evaluate + failure_modes (T7) + llm_eval (T8، تشغيل يدوي) |
| `src/generator/` | ✅ مكتمل | generate_data |
| `src/integrations/` | ✅ مكتمل | zain_cash (محفظة وهمية) + wallet_flow (اعتراض) |
| `src/agents/` | ✅ مكتمل | intake (T6) + dialogue (T11) + training (T12): صفر اتصال بالقاعدة |
| `src/demo_check.py` | ✅ مكتمل | فحص جاهزية الديمو: 6 بنود PASS/FAIL بالإنجليزي (T10) |
| `web/` | ✅ مكتمل | index (ستايل Zain Cash) + log + results + style.css + app.js |
| `demo/` | ✅ مكتمل | 6 سيناريوهات + SCRIPT.md (عرض 5 دقائق + قسم اختياري T11/T12) + QA.md (16 سؤال) |
| `prompts/` | ✅ مكتمل | صياغات توليد البيانات T3 منسوخة حرفاً من ملحق ROADMAP + README مصدرها |
| `docs/JUDGE_REQUIREMENTS_REFERENCE.md` | ✅ مكتمل | مرجع ثابت لمتطلبات اللجنة من Topic_Briefs (73 بنداً: 29 متطلبات + 18 تحقق يدوي + 15 سؤال + 11 ملاحظة) — لا يُعدَّل |

## الاختبارات

- **294 اختبار** ينجح (268 سابق + 26 جديدة لـ T12: 24 تدريب + 2 واجهة)
- 0 فشل
- `python -m src.demo_check` → **ALL CHECKS PASSED (6/6)** بوضع `COACH_MODE=llm` والمفتاح (استدعاء Gemini حيّ: `gemini-3.7-flash`)
- إعادة تحقق 2026-10-02 (بعد T11/T12): **5/6** — كل الفحوصات المحلية PASS (294 اختبار بالداخل) و`gemini_connection` رجّع أخطاء **من طرف Google** (503 ذروة طلب / 504 تجاول 10 ثوانٍ) ثلاث مرات متتالية، وفحص `fallback` أنجح بنفس التشغيل — أعديه وقت أهدأ للحصول على 6/6
- مطابقة نصوص المشروع مع `docs/JUDGE_REQUIREMENTS_REFERENCE.md` (2026-10-02): تصحيح صياغة `.env` بـ DISCLOSURE وprivacy_notes (كانت "خارج `.gitignore`" والصحيح "مُدرَج بـ`.gitignore`")، تحديث "T0–T10" → "T0–T12"، تحديث "13 endpoints" → 16، سطر المرجع بجدول وثائق README، وإزالة `docs/eval_results.json` من `.gitignore` عشان ينرفع مع المستودع كدليل تقييم
- امتداد المطابقة (نفس التاريخ): الفحوصات السلبية الأربعة نجحت كلها (لا قفل إجباري بـ`src/`، لا استدعاء LLM بـ`src/detection/`، صفر هواتف حقيقية بالبيانات، صفر مفاتيح `AIza` بالمستودع) + README (تصحيح سطر `eval/` + إضافة `prompts/` للشجرة) + `demo/QA.md` اكتمل بـ3 أسئلة من المرجع (س17 الاعتراض قبل التنفيذ، س18 توليد البيانات، س19 دليل المقابلات ✋) + إصلاح إملاء بـس5
- تدقيق شامل للمسارات والأرقام (نفس التاريخ): فحص 201 مسار ملف بالمرجع (تصحيح مسارين + أمر csv بديل عن pandas لأنه غير مثبّت) + **تصحيح تركيب البيانات بكل الوثائق**: 3,095/152 هي سجلات dev بس والمعزول 1,561/56 (المجموع 4,656 و208) — صححت بـ QA/REFERENCE/summary_latest/project_summary/PLAN + تجديد `project_explanation_ar.md` (شجرة + 16 endpoint + مربعا الحوار والتدريب + 294 بدل 141 + إزالة pandas) + إعادة كتابة `questions_ar.md` (كان يقول "سأصلح الكود" والحل منرفوع من زمان + "النشر خارج نطاق" وموجود render.yaml) + سطر تاريخي بملفات T5/T5b/T6
- مسح شامل لسكربتات غير عربية (نفس التاريخ): فحص `unicodedata` لكل ملفات النصوص (101 ملف) اكتشف تلف حروف بـ6 مواقع وإصلاحها: `run_project_ar.md` (Cyrillic بقائمة + كلمة إنجليزية زائدة)، `JUDGE_REQUIREMENTS_REFERENCE.md` (Kana بسطر Data 3)، `src/api/main.py` (Katakana بتعليق)، `src/generator/generate_data.py` (CJK بعيّنة نص حر — تأكدنا أنصالة لم تسرّب لأي CSV أو DB)، `tests/test_wallet.py` (Cyrillic بتعليق)، `src/demo_check.py` (Thai بتعليق) — الفحص بعد الإصلاح: صفر نتائج
- تدقيق المسارات وعدد الـ endpoints بكل الوثائق (نفس التاريخ): فحص 593 مسار backtick بجميع ملفات md (117 علم — 103 بسبب فحص من جذر غلط، و14 حقيقية كلها مخططات ROADMAP لم تُبنَ بأسمائها أو مخرجات مؤجلة يدوياً) + التأكد برمجياً من **16 مسار API فعلياً** بمقارنة `app.routes` (وتصحيح `{id}`→`{user_id}` بجدول النقاط و«15 نقطة»→«16» بـstatus_summary) + إضافة ROADMAP بند **«مطابقة أسماء الخطة بأسماء التنفيذ»** (6 صفوف: sample_messages→templates، llm_client/prompts/validators→llm.py+coach.py، try_llm→llm_eval، llm_gen→generate_data، llm_raw/manifest→prompts/data_gen، catalogue_changes→scam_catalogue+failure_modes) حتى ما يبان مسارات ناقصة لحكم يفحصها
- تنفيذ أوامر فحص المرجع كما يشغلها الحكم (نفس التاريخ): الأوامر كلها تشتغل وتعطي المُعلن — عدّاد `users.csv`=30، صفر هواتف `07[0-9]{8}`، صفر استدعاءات LLM بالكشف — **وإصلاح أمرَين**: نمط `lock` كان يطابق داخل كلمة `"blocked"` بـ`models.py:270` (نتيجة 1 مو المُعلن صفر — زوّدنا `\b` حول `lock`/`freeze`) + تجبين صفّين بالمرجع (أنابيب `|` داخل خلية كسرت الجدول 7×5 بدل 5×5) — فحص الجداول بعد الإصلاح: صفر مشاكل
- رفع git (2026-10-02): الشجرة نظيفة و8 commits كلها مرفوعة على `origin/main` — توثيق كامل بـ`docs/git_upload_report.md` (المرفوع/غير المرفوع/الـ CRLF/الفحص الأمني)، مع خطّاف `.cac/hooks/pre-commit` يمنع أي commit يحتوي `.env` أو مفتاحاً حقيقياً

## أسئلة مفتوحة

- هل تتدرّبين على `demo/SCRIPT.md` مرتين قبل اللجنة وتعدّلين عليه لو حبيتي؟
- هل تبي تعديلات على ألوان Zain Cash بالواجهة؟ (متغيرات CSS: `--zain-purple` / `--zain-purple-light`)
- هل نراجع نتائج `docs/failure_modes.md`؟ (3 احتيالات فاتت حقيقة — مو تجميل)
- متى نشغّل `python -m src.eval.llm_eval`؟ (يحتاج `COACH_MODE=llm` بـ `.env` + المفتاح + رصيد)
- ✋ `docs/user_research.md` جاهز بانتظار مقابلاتك (3–5 أشخاص، الأسئلة جاهزة بداخله).
- ✋ `docs/data_review.md`: المرور الأول (آلي) مكتمل — ناقص جدولك اليدوي (50 صف + مراجع ثاني 20).
