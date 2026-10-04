# المرجع الشامل لمتطلبات لجنة Agentic AI Challenge Iraq — موضوع 01

هذا الملف مرجعي. لا يُعدَّل. يصف المتطلبات كما وردت في ملف التحدي الرسمي.

الملف مصدره `Topic_Briefs.pdf` المنشور من اللجنة (8 صفحات، موسوم: `DRAFT FOR REVIEW | 17/09/2026`).

---

## 1. الفحوصات الإجبارية (Gating Checks)

> ملاحظة تمهيدية: هذه الفحوصات شرط عبور قبل أي درجة. فشل واحد = استبعاد.
> النص المصدري: "Before scoring, every submission must clear four checks"

| # | المطلوب (النص الإنجليزي الحرفي) | الشرح بالعربية | كيف يُتحقق | أين يوجد الدليل في المشروع |
|---|---|---|---|---|
| 1 | "A repository with commit history spanning the build period." | مستودع (GitHub) فيه سجل commits يغطي فترة بناء المشروع، مو مجموعة ملفات بس. | افتح رابط المستودع واضغط تبويب `Commits` — أو نفّذي `git log --oneline --date=short` داخل المجلد. لازم يبيّن تاريخين/فترة ممتدة. | المستودع: `https://github.com/hibathafer/fraud-protection-agent.git` — صفحة History بتها. |
| 2 | "A live run on judge-supplied input." | تشغيل حي أمام اللجنة، بإدخال يحدده الحكم بنفسه (مو سيناريو محضّر سلفاً). | شغّلي `python -m uvicorn src.api.main:app --reload` → افتحي `http://localhost:8000` → الصقي إدخال من اختيار اللجنة: JSON عبر `POST /api/assess` (صفحة `/docs`) أو نص حر عبر `POST /api/scenario_text`. | الواجهة `web/index.html` + صفحة OpenAPI على `http://localhost:8000/docs` + أداة الفحص `src/demo_check.py`. |
| 3 | "Full disclosure of models, tools and data." | إفصاح كامل: النماذج، الأدوات، المكتبات، مصادر البيانات، ومساعدات الـ AI المستخدمة بالبناء. | افتحي `docs/DISCLOSURE.md` وتأكدي أن كل أداة ونموذج ومصدر بيانات مذكور فيه، بما فيها مساعد الـ AI اللي بنيتِ فيه المشروع. | `docs/DISCLOSURE.md`. |
| 4 | "At least three documented failure modes with how you handle them." | ثلاث حالات فشل على الأقل، كل واحدة موثقة: شنو صار + شلون تعاملتوا معاه. | افتحي `docs/failure_modes.md` — أو شغّلي `python -m src.eval.failure_modes` — أو افتحي جدول حالات الفشل بـ `web/results.html`. | `docs/failure_modes.md` + `src/eval/failure_modes.py` + `GET /api/failure_modes` (يظهر بواجهة `web/results.html`). |

---

## 2. المتطلبات الإجبارية لموضوع 01 (Must Have)

> ملاحظة تمهيدية: كل بند هنا مذكور حرفياً في ملف التحدي ضمن قسم "Must have" لموضوع 01.

| # | المطلوب (النص الإنجليزي الحرفي) | الشرح بالعربية | كيف يُتحقق | أين يوجد الدليل في المشروع |
|---|---|---|---|---|
| 1 | "Intervenes before the transaction completes, not after." | الاعتراض يصير **قبل** تنفيذ التحويل، مو بعد ما يروح المبلغ. | جرّبي تحويلاً لسيناريو حجز: `POST /api/wallet/transfer` → لازم الطلب يرجع **معلّقاً** مع رسالة تحذير، والتنفيذ يصير بس بعد ضغط "أكمل التحويل". | `src/integrations/wallet_flow.py` (طبقة الاعتراض) + نافذة التحذير بـ `web/index.html` + اختبارات `tests/test_wallet.py` + `POST /api/wallet/transfer` بـ `src/api/main.py`. |
| 2 | "Explains the specific risk in plain Iraqi Arabic, with no jargon." | شرح الخطر **بالمحدد** (شنو بالضبط مريب) بلهجة عراقية بسيطة، بدون مصطلحات تقنية. | شغّلي أي سيناريو مريب بالواجهة واقرا الرسالة الظاهرة — لازم تكون بالدارجة ومبيّنة السبب (مثلاً "أول تحويل لهالشخص" مو "unusual pattern detected"). | `src/coaching/templates.py` (قوالب 8 أنماط + عامة، ≤60 كلمة) + `src/coaching/coach.py` + اختبارات `tests/test_coaching.py`. |
| 3 | "Lets the user proceed if they choose, and records that choice." | المستخدم يقدر يكمل التحويل إذا بغت — بدون قفل — **وكل اختيار يتسجل**. | بالواجهة: بعد التحذير اضغطي "أكمل التحويل" → بعدها افتحي `web/log.html` — لازم يبيّن اختيارك ووقته وحالته النهائية. أو نفّذي `GET /api/log/export`. | `POST /api/choice` بـ `src/api/main.py` + جدول `decision_log` بـ `src/db.py` + واجهة السجل `web/log.html` + اختبارات `tests/test_api.py`. |
| 4 | "Detection uses clear rules or simple statistics that a reviewer can read and understand." | الكشف من قواعد/إحصاءات بسيطة يقدر **قارئ بشري** يفتحها ويقراها ويفهمها — مو صندوق أسود. | افتحي `src/detection/rules.py` — لازم تشوفين القواعد التسع مكتوبة بجمل عربية واضحة مع حدودها الرقمية، وكل سبب قرار مكتوب بالعربي. | `src/detection/rules.py` (9 قواعد) + `src/detection/engine.py` + `src/detection/features.py` + كتالوج الأنماط `data/scam_catalogue.json` + اختبارات `tests/test_rules.py` و`tests/test_engine.py`. |

---

## 3. خارج النطاق (Out of Scope)

> ملاحظة تمهيدية: هذه بنود إذا وُجدت في المشروع = خصم مباشر.

| # | المطلوب (النص الإنجليزي الحرفي) | الشرح بالعربية | كيف يُتحقق (فحص سلبي: نتأكد أنه غير موجود) | أين يوجد الدليل في المشروع |
|---|---|---|---|---|
| 1 | "Blocking transactions without the user's consent." | أي قفل/منع إجباري للتنفيذ **بدون موافقة المستخدم** ممنوع — الحجز لازم يظل قابلاً للمتابعة دائماً. | ابحثي بالكود عن مسار يمنع التنفيذ قسراً: `Select-String -Path src\*.py -Pattern "force_block\|\b(lock\|freeze)\b"`. النتيجة المطلوبة: صفر. وتأكد بالتجربة إنو زر "أكمل التحويل" متاح في كل حالات الحجز. | دليل على الغياب: `src/integrations/wallet_flow.py` (الحجز = تأخير مع خيار دائم) + `tests/test_wallet.py` (يثبت توفر المتابعة). |
| 2 | "Detection should rest on rules and thresholds a reviewer can read; the model's job is the coaching." | الكشف لازم يكون قواعد وحدوداً مقروءة — **شغل النموذج اللغوي هو التوجيه والشرح فقط**، مو الكشف. | ابحثي عن استدعاءات نموذج لغوي داخل طبقة الكشف: `Select-String -Path src\detection\*.py -Pattern "genai\|generate_content\|llm"`. النتيجة المطلوبة: صفر — أي استدعاء LLM يكون بس في `src/coaching/` أو `src/agents/`. | `src/detection/` (معزول عن أي LLM) مقابل `src/coaching/llm.py` (مكان الاستدعاء الوحيد) + `tests/test_engine.py` و`tests/test_llm_safety.py`. |

---

## 4. معايير التقديم القوي (Strong Submission)

> ملاحظة تمهيدية: هذه بنود لا تُلزم بالنجاح، لكنها ترفع التقييم.

| # | المطلوب (النص الإنجليزي الحرفي) | الشرح بالعربية | كيف يُتحقق | أين يوجد الدليل في المشروع |
|---|---|---|---|---|
| 1 | "Low false positives." | إنذارات كاذبة قليلة — التنبيه على عملية بريئة يخسر المستخدم. | افتحي `docs/evaluation_report.md` ودور على نسبة FPR (False Positive Rate) على مجموعة الاختبار المعزول — لازم تكون منخفضة ومذكورة بأرقام TP/FP. | `docs/evaluation_report.md` + `docs/eval_results.json` + `docs/test_runs.log` (سطر التشغيل الموقّع). |
| 2 | "An agent that interrupts honest transactions gets switched off by the user within a week." | (توضيح البندة السابقة) وكيل يقاطع المعاملات الصادقة يطفيه المستخدم خلال أسبوع — عشان كذا الانضباط بالإنذارات أولوية. | نفس الفحص أعلاه: قارني رقم FPR مع هدف 5% المكتوب بتقرير التقييم، وتأكدي أن التقرير يشرح أسباب كل تنبيه كاذب. | `docs/evaluation_report.md` (قسم تحليل الـ FP) + `docs/data_review.md`. |
| 3 | "A test set with labeled scam and non-scam scenarios, and the precision and recall you achieved on it." | مجموعة اختبار عليها تصنيف (احتيال/غير احتيال) + رقمي precision وrecall محسوبين عليها. | افتحي `data/test_sealed/` (التصنيفات بالملفات) و`docs/evaluation_report.md` (الأرقام) — لازم تلاقي Precision وRecall بأرقام واضحة مع TP/FP/FN/TN. | `data/test_sealed/users.csv` و`data/test_sealed/transactions.csv` + `docs/evaluation_report.md` + `docs/eval_results.json`. |
| 4 | "Coaching that sounds like a person from Iraq, not a translated bank notice." | رسائل التوعية لازم تشبه إنسان عراقي — مو إشعار بنك منقول من الإنجليزي. | اقرئي القوالب مباشرة أو شغّلي سيناريو واقرا الرسالة بعينك — لازم تكون دارجة (مثل "گاعد تخسر فلوسك" مو "يرجى التوقف عن المتابعة"). | `src/coaching/templates.py` + نافذة التحذير بـ `web/index.html` + `demo/QA.md` (أسئلة اللجنة عن اللهجة). |

---

## 5. متطلبات البيانات (Data)

> ملاحظة تمهيدية: متطلبات البيانات الاصطناعية وطريقة توليدها.

| # | المطلوب (النص الإنجليزي الحرفي) | الشرح بالعربية | كيف يُتحقق | أين يوجد الدليل في المشروع |
|---|---|---|---|---|
| 1 | "Use an LLM to generate synthetic transaction histories for at least 20 users, with scam scenarios planted in some of them, from a structure you define." | توليد سجلات معاملات وهمية بـ LLM لـ 20 مستخدم على الأقل، وفيها سيناريوهات احتيال مزروعة ببعضهم، من بنية تحددها أنتِ. | عُدّ المستخدمين: `python -c "import csv; print(sum(1 for _ in csv.DictReader(open('data/synthetic/users.csv', encoding='utf-8'))))"` — لازم يطلع 20 أو أكثر. وشوفي أعمدة التصنيف/السيناريوهات بـ `data/synthetic/transactions.csv`. | `data/synthetic/users.csv` + `data/synthetic/transactions.csv` + كود التوليد `src/generator/generate_data.py` + صياغات التوليد `prompts/data_gen/`. |
| 2 | "Research real Iraqi scam patterns and turn them into a written catalogue your detection layer uses." | بحث عن أنماط الاحتيال العراقي الحقيقية وتحويلها لكتالوج مكتوب يستخدمه الكشف. | افتحي `data/scam_catalogue.json` — لازم يحتوي أنماط احتيال مكتوبة (عربي) بكل تفاصيلها، وتأكدي أن القواعد تستورد منه فعلاً. | `data/scam_catalogue.json` (8 أنماط) + استيراده بـ `src/detection/rules.py` + اختبارات `tests/test_catalogue.py`. |
| 3 | "No real customer data." | ممنوع أي بيانات حقيقية: لا أرقام هواتف، لا أسماء حقيقية، لا سجلات عملاء فعلية — لك أو لغيرك. | ابحثي بأرقام الهواتف العراقية داخل البيانات: `Select-String -Path data\synthetic\*.csv -Pattern "07[0-9]{8}"`. النتيجة المطلوبة: صفر. وكل الأسماء والعناوين لازم تكون وهمية. | `docs/privacy_notes.md` (حدود الخصوصية) + `docs/data_review.md` (مراجعة العينة) + `docs/DISCLOSURE.md` (مصادر البيانات). |

---

## 6. معايير التقييم الرسمية (Judging Weights)

> ملاحظة تمهيدية: هذه الأوزان تحدد أين يستحق المشروع بذل الجهد.
> النص المصدري: "Complexity alone does not score. Weights for the build and demo round:"

| المعيار | الوزن | ما تبحث عنه اللجنة (النص الحرفي) | كيف يُثبت في المشروع | أين يوجد الدليل |
|---|---|---|---|---|
| Working prototype and reliability | 25% | "Does it run live on input the judges supply, and does it hold up?" | تشغيل حي باختيار اللجنة: JSON عبر `POST /api/assess` أو نص حر عبر `POST /api/scenario_text`، والنظام يرجّع قراراً ورسالة بدون انهيار. الفحص الشامل: `python -m src.demo_check`. | الواجهة `web/index.html` + `/docs` (OpenAPI لكل النقاط) + `src/demo_check.py`. |
| Technical judgment and architecture | 20% | "Right tool for the job, sensible failure handling, no unjustified complexity" | بنية مقسمة بوضوح: كشف (قواعد) / توجيه (قوالب+LLM اختياري) / وكلاء / تكامل محفظة — وفشل النموذج اللغوي يرجع تلقائياً للقالب، بدون مكتبات أو تعقيد غير مبرر. | `src/` (التقسيم) + `docs/privacy_notes.md` (حدود الـ LLM) + `docs/failure_modes.md` (معالجة الفشل) + `docs/DISCLOSURE.md` (قائمة الأدوات القصيرة). |
| Problem and impact | 20% | "A real user, a real problem, evidence you spoke to someone" | وصف مشكلة حقيقية (هندسة اجتماعية على مستخدمي المحافظ العراقية) + **دليل إنك سألت أشخاص فعلاً**: مقابلات مستخدمين موثقة. | `docs/user_research.md` (المقابلات) + `docs/project_summary_ar.md` وصف المشكلة + `ROADMAP.md` (تحليل الهدف). |
| Grounding, security and responsibility | 15% | "Outputs traceable to data, safe failure, privacy handled" | كل سبب قرار مرتبط بقاعدة/نمط مكتوب يُردَّ إليه؛ فشل آمن (fallback) مثبت؛ وخصوصية معالَجة: لا PIN بالسجل، لا بيانات حقيقية، نصوص دخيلة تُعامل كبيانات غير موثوقة. | `src/detection/rules.py` (أسباب قابلة للردّ) + `docs/privacy_notes.md` + `docs/failure_modes.md` + اختبارات `tests/test_llm_safety.py`. |
| Evaluation evidence | 15% | "A held-out test set and honest results on it" | مجموعة اختبار معزولة (ما ضُبط عليها) + أرقام صادقة عليها: Precision/Recall/FPR مع الحدود مذكورة بصدق. | `data/test_sealed/` + `docs/evaluation_report.md` + `docs/eval_results.json` + `docs/test_runs.log`. |
| Demo clarity | 5% | "Judges understand what it does in the first minute" | سكربت عرض بخمس دقائق تشرح المشكلة والحل بأول جملة + سيناريوهات جاهزة بالضغط الواحد. | `demo/SCRIPT.md` + `demo/QA.md` + ملفات السيناريوهات الستة بـ `demo/*.json` + `README.md`. |

---

## 7. القواعد العامة لكل المواضيع (Rules for Every Topic)

> ملاحظة تمهيدية: هذه قواعد تنطبق على كل مشاريع التحدي.

| # | القاعدة (النص الحرفي) | الشرح بالعربية | كيف نلتزم بها |
|---|---|---|---|
| 1 | "Leverage what LLMs can do. Every topic is about using and deploying foundation models: prompting, retrieval, tool use, agents and evaluation. The question each brief asks is how far you can take a modern model on a real problem." | استغلال حقيقي لقدرات النماذج الأساسية: برومبتينج، استرجاع، استدعاء أدوات، وكلاء، وتقييم — مو استدعاء شكلي. | استدعاء حيّ للنموذج بـ `src/coaching/llm.py` (عبر `google-genai`) + وكلاء حقيقيون `src/agents/` (Intake/Dialogue/Training) + تقييم منظم `src/eval/` (evaluate/llm_eval/failure_modes/metrics). |
| 2 | "Simulate your data with an LLM. No real customer records, identity documents or transaction histories, yours or anyone else's. Use a model to generate the transactions, tickets, profiles or documents your brief needs. Give it the structure and the edge cases you want, generate more than you need, check a sample by hand, and hold part back for testing." | توليد البيانات كله بـ LLM من بنية محددة مسبقاً — صفر سجلات حقيقية — توليد أكثر من الحاجة، مراجعة عينة يدوياً، وحجز جزء للاختبار. | التوليد الهجين بـ `src/generator/generate_data.py` (بذورة `random.seed(42)`) + الصياغات بـ `prompts/data_gen/` + المراجعة اليدوية `docs/data_review.md` + الجزء المحجوز `data/test_sealed/`. |
| 3 | "Build a test set. Every brief asks for a held-out set your system was not tuned on, and for your results on it. A demo without numbers is a demo, not evidence." | مجموعة اختبار معزولة ما ضُبط النظام عليها + نتائج معلنة عليها. عرض بلا أرقام = عرض مو دليل. | `data/test_sealed/` (10 مستخدمين معزولين) تستخدم مرة واحدة بس بأمر المستخدمة، ونتائجها المنشورة مع تاريخ ووقت التشغيل. الأرقام مو مخفية — فيها السيئ والجيد. | 
| 4 | "Iraqi Arabic is the default. Users in these briefs speak and type in dialect. Show how your system handles that." | اللهجة العراقية هي الافتراضية — النظام لازم يفهم ويتكلم الدارجة. | كل القوالب والرسائل بالدارجة (`src/coaching/templates.py`) + قبول نص حر باللهجة عبر `POST /api/scenario_text` و`POST /api/chat` + اختبارات `tests/test_text_norm.py` و`tests/test_intake.py`. |
| 5 | "Disclose everything you used. Models, tools, libraries, data sources and AI coding assistants. Using AI to build is expected. Hiding it is not." | اكشف كل شي استخدمته: النماذج، الأدوات، المكتبات، مصادر البيانات، ومساعدات الـ AI. استعمال الـ AI بالبناء متوقع — إخفاؤه مو مقبول. | `docs/DISCLOSURE.md` يسرد: نموذج Gemini (وموديله)، Python/FastAPI/SQLite/pandas/Pydantic، google-genai، مصادر البيانات (مولّدة)، ومساعد الـ AI (Claude). |
| 6 | "Simple and reliable beats complex. A focused system that works will score above an ambitious architecture that does not." | البساطة والموثوقية تفوز على التعقيد — نظام مركّز يشتغل أفضل من معمارية طموحة ما تشتغل. | بنية صغيرة مقصودة: FastAPI + SQLite + محرك قواعد بايثون — بدون vector database، بدون RAG، بدون microservices، وكل مكتبة بموجب مبرر مكتوب بـ `ROADMAP.md` (القرارات المعمارية). |

---

## 8. قائمة التحقق اليدوية (Verification Playbook)

> هذا القسم مخصص للمستخدمة، وليس للحكم: خطوات بسيطة تقدرين تنفذينها بنفسك بدون خبرة عميقة.

| المطلوب | الخطوة اليدوية للتحقق | النتيجة المتوقعة | إذا فشلت، ما المشكلة المحتملة؟ |
|---|---|---|---|
| الفحص 1: المستودع وسجل الـ commits | افتحي الرابط على GitHub واضغطي تبويب `Commits` (أو جوه المشروع: `git log --oneline --date=short`). | سجل commits كثيرة موزعة على أيام فترة البناء. | سجل قصير/دفعة وحدة = الفحص الإجباري الأول معرّض للاستبعاد — راجعي الـ commits الناقصة. |
| الفحص 2: التشغيل الحي | شغّلي `python -m uvicorn src.api.main:app --reload` وافتحي `http://localhost:8000`. | الواجهة تفتح وتستقبل سيناريو فوراً. | رسالة خطأ بالتشغيل = مشكلة بيئة (Python/مكتبات) — انسخي الخطأ وابتعثيه. |
| الفحص 2: إدخال JSON من اللجنة | افتحي `http://localhost:8000/docs` → جربي `POST /api/assess` بجسم JSON فيه مبلغ ومستلم جديد ووقت. | يرجّع قراراً (allow/warn/hold) مع أسباب بالعربي. | خطأ 422 = حقل ناقص بالـ JSON — راجعي حقول `src/models.py`. |
| الفحص 2: نص حر باللهجة | جربي `POST /api/scenario_text` وحاولي نص بالدارجة مثل: "گاعد يهديني بيه شي من داعي". | تقييم مهيكل أو سؤال توضيحي لو ناقصة معلومة. | "ما فهمنا النص" بشكل متكرر = مشكلة بـ Intake — راجعي `tests/test_intake.py`. |
| الفحص 3: الإفصاح | افتحي `docs/DISCLOSURE.md`. | كل نموذج/أداة/مكتبة/مصدر بيانات + مساعد الـ AI مذكورين. | أي أداة ناقصة = أضيفيها قبل التسليم (الإخفاء = استبعاد). |
| الفحص 4: حالات الفشل | افتحي `docs/failure_modes.md` أو `web/results.html` (جدول حالات الفشل). | 3 حالات على الأقل (عندنا 6) — كل واحدة: شنو صار + شلون التعامل. | أقل من 3 أو بدون "كيف تعاملتوا" = فشل فحص إجباري. |
| Must have 1: الاعتراض قبل التنفيذ | جرّبي سيناريو حجز من الصفحة الرئيسية (تحويل لمستلم جديد بمبلغ كبير). | الشاشة **تتوقف قبل الإيصال** + نافذة تحذير، والإيصال يطلع بعدها فقط إذا كمّلتي. | إذا نفذ مباشرة بدون توقف = خرق مباشر لـ Must have رقم 1. |
| Must have 2: رسالة عراقية بدون مصطلحات | اقرؤي رسالة التحذير الظاهرة بالواجهة. | لهجة دارجة + سبب محدد، بدون كلمات إنجليزية/تقنية. | رسالة رسمية/مترجمة = راجعي `src/coaching/templates.py` (وإذا بالوضع llm، تحقق من مخرجات النموذج). |
| Must have 3: الاختيار يتسجل | اضغطي "أكمل التحويل" بعدين افتحي `http://localhost:8000/log.html`. | اختيارك ظاهر بالسجل مع تاريخ ووقت وحالته النهائية. | ما ظهر = مشكلة بـ `POST /api/choice` أو جدول السجل — راجعي `tests/test_api.py`. |
| Must have 4: قواعد مقروءة | افتحي `src/detection/rules.py` واقرا القواعد. | قواعد مكتوبة بجمل عربية + حدود رقمية واضحة (30 و60) + أسباب عربية. | أرقام غامضة أو أسباب إنجليزية = راجعي التوثيق قبل العرض. |
| Out of scope 1: لا قفل بدون موافقة | ابحثي: `Select-String -Path src\*.py -Pattern "force_block\|\b(lock\|freeze)\b"`. | صفر نتائج + تأكيد عملي إن زر "أكمل" متاح بأي حالة حجز. | طلع مسار قفل = خرق Out of scope — اشيليه. |
| Out of scope 2: كشف بدون LLM | ابحثي: `Select-String -Path src\detection\*.py -Pattern "genai\|generate_content"`. | صفر نتائج (الـ LLM بس بـ coaching/agents). | طلع استدعاء = خرق Out of scope — انقله لطبقة التوجيه. |
| Strong 1+2: الإنذارات الكاذبة | افتحي `docs/evaluation_report.md` ودور على كلمة `FPR`. | رقم واضح (هدف المشروع ≤5%) + تفسير كل FP. | الرقم ناقص أو مو على مجموعة معزولة = راجعي `docs/test_runs.log`. |
| Strong 3: Precision وRecall | بنفس التقرير، دور على `Precision` و`Recall`. | أرقام P/R بأكملها مع TP/FP/FN/TN + discussion صادق للحدود. | أرقام بدون TP/FP = حساب ناقص — نفّذي `python -m src.eval.evaluate` وقارني. |
| Data 1: 20 مستخدم على الأقل | `python -c "import csv; print(sum(1 for _ in csv.DictReader(open('data/synthetic/users.csv', encoding='utf-8'))))"` | رقم ≥ 20 (المشروع: 20 dev + 10 test معزول). | أقل من 20 = خرق بند Data — أعيدي التوليد بـ `src/generator/generate_data.py`. |
| Data 2: الكتالوج العراقي | افتحي `data/scam_catalogue.json`. | أنماط احتيال مكتوبة (8 أنماط) + القواعد تستورد منها. | الكتالوج فاضي/مكرر = راجعي `tests/test_catalogue.py`. |
| Data 3: لا بيانات حقيقية | `Select-String -Path data\synthetic\*.csv -Pattern "07[0-9]{8}"`. | صفر نتائج (لا هواتف حقيقية). | طلع رقم = خرق خصوصية — عوّضيه فوراً |
| فحص شامل قبل أي عرض | `python -m src.demo_check` | كل الفحوصات تنجو (قاعدة، اختبارات، مفتاح، اتصال، fallback، سيناريوهات). | فشل `gemini_connection` فقط = ضغط وقت مؤقت عند Google — أعيديه وقت أهدأ؛ فشل غيره = انسخي الخطأ. |

---

## 9. الأسئلة المتوقعة من اللجنة (Anticipated Q&A)

| # | السؤال | الجواب المثالي | أين يوجد الدليل | الأهمية |
|---|---|---|---|---|
| 1 | كيف يمنع النظام عملية احتيال وهي تحدث "قبل" ما يكتمل التحويل؟ | النظام طبقتين: كشف بقواعد بايثون + تنسيق بلهجة عراقية. الطلب يمر من `POST /api/wallet/transfer` قبل التنفيذ — إذا قرر "حجز"، تعلّق العملية وتظهر نافذة تحذير. المستخدم يقرر: "أكمل" → تنفيذ وإيصال، "إلغاء" → ما يصير شي. الاعتراض مدمج بمسار التنفيذ نفسه، مو إضافة بعده. | `src/integrations/wallet_flow.py` + `web/index.html` + `tests/test_wallet.py` | عالية |
| 2 | شلون تثبتون إن النموذج اللغوي ما يقدر يغيّر قرار الكشف؟ | التصنيف من `src/detection/` — بايثون فقط، بدون أي استدعاء لغوي. مخرجات النموذج تدخل بمسار التوجيه/الحوار بس، وتمر على تحقق (validate) قبل العرض. اختبارات صريحة تثبت: أي رسالة نموذج ما تغير score ولا تصنيف، ودالة `/api/chat` ما تكتب بجدول القرار أصلاً. | `tests/test_dialogue.py` (test_chat_does_not_change_decision) + `tests/test_engine.py` + `docs/privacy_notes.md` | عالية |
| 3 | شنو رقم الإنذارات الكاذبة عندكم؟ | FPR = **3.2%** على مجموعة الاختبار المعزول (1,561 معاملة، 56 احتيال) — تحت هدف 5%. وحجز الـ hold لحاله FPR = 0.1%. التقرير يشرح إنو كل تنبيه كاذب مبرر (مثل مستلم جديد أول مرة) — الموازنة مقصودة لصالح قلة الإزعاج. | `docs/evaluation_report.md` + `docs/test_runs.log` | عالية |
| 4 | وين أرقام precision وrecall؟ | any_alert: **P = 0.342، R = 0.446** — hold_only: **P = 0.913، R = 0.375** — macro_recall = 0.478. تُذكر بصراحة مع سببها: الفئة الاحتيالية نادرة (3.6%) فتنزل الـ precision، والاختيار مقصود: دقة الحجز عالي 91% + إنذارات كاذبة منخفضة. | `docs/evaluation_report.md` + `docs/eval_results.json` | عالية |
| 5 | كيف تتعاملون مع اللهجة العراقية مو الفصحى؟ | "Iraqi Arabic is the default": كل القوالب والرسائل بالدارجة (8 أنماط احتيال + عامة). والنص الحر (سؤال المستخدم أو سيناريو) ينقال لـ Intake يحوّله لبيانات مهيكلة، وإذا ناقصة معلومة يرجّع سؤالاً توضيحياً — والنموذج اللغوي فوق القوالب اختياري دائماً. | `src/coaching/templates.py` + `src/agents/intake.py` + `tests/test_intake.py` + `tests/test_text_norm.py` | عالية |
| 6 | شنو يصير إذا النموذج اللغوي وقع أو ما متاح؟ | Fallback تلقائي للقالب الجاهز — النظام ما يوقف أبداً. مثبت باختبارات (LLM outage → template)، ووضع `template` أصلاً يشتغل بدون مفتاح. نفس آلية الأمان هذه موثقة كإحدى حالات الفشل. | `src/coaching/coach.py` + `tests/test_coach_mode.py` + `docs/failure_modes.md` | عالية |
| 7 | شنو حالات الفشل عندكم وشنو تعاملكم معاها؟ | ست حالات موثقة (المطلوب 3 كحد أدنى): فشل النموذج اللغوي، نص ما يتفهم، بيانات ناقصة، مستخدم ما يكمل، إدخال حقن تعليمات، حدود قياسية. كل حالة: الوصف + السبب + آلية التعامل + ناتج الاختبار. | `docs/failure_modes.md` + `src/eval/failure_modes.py` + `web/results.html` | عالية |
| 8 | شلون ولّدتوا البيانات؟ ووين الـ prompts؟ | توليد هجين LLM + بايثون ببذورة ثابتة `seed=42`: 30 مستخدم — سجلات التطوير بـ `data/synthetic/` (20 مستخدم، 3,095 معاملة، 152 احتيال) والمعزول بـ `data/test_sealed/` (10 مستخدمين، 1,561 معاملة، 56 احتيال). صياغات التوليد محفوظة بـ `prompts/data_gen/`، ومعاينة يدوية موثقة بـ `docs/data_review.md`. | `prompts/data_gen/` + `src/generator/generate_data.py` + `docs/data_review.md` | متوسط |
| 9 | إذا قال النظام "حجز" — المستخدم محبوس؟ | لا. المستخدم **دايماً** تقدر تكمل — هذا مطلب صريح: "Lets the user proceed if they choose". ما في قفل ولا تجميد ولا منع إجباري، وكل اختيار (أكمل/إلغاء) يتسجل بسجل تدقيق مع حالته النهائية. | `POST /api/choice` + `web/log.html` + `tests/test_wallet.py` | عالية |
| 10 | شنو خصوصيتكم؟ وشنو اللي يوصل للنموذج اللغوي؟ | ما يوصل للنموذج: رمز الـ PIN أبداً، أي بيانات حقيقية، أو حقول التصنيف (is_scam). وكل نص دخيل يُعامل كبيانات غير موثوقة (مثبت ضد Prompt Injection). التفاصيل كاملة بوثيقة خصوصية مخصصة. | `docs/privacy_notes.md` + `tests/test_llm_safety.py` + `tests/test_llm_eval.py` | عالية |
| 11 | كيف تثبتون إن الأرقام من مجموعة ما ضبطتوا النظام عليها؟ | مجموعة `data/test_sealed/` منفصلة (10 مستخدمين) استُخدمت **مرة وحدة** بأمر المستخدمة وقت التقييم النهائي — ما انفتحت أثناء الضبط. ونتيجة التشغيل موقّعة بسطر timestamp داخل `docs/test_runs.log` بتاريخ 2026-10-01. | `data/test_sealed/` + `docs/evaluation_report.md` + `docs/test_runs.log` | عالية |
| 12 | سويتوا شي من الـ Stretch؟ | نعم: **وضع تدريب** — محادثة تعليمية وهمية يتدرب فيها المستخدم يفرّق بين محادثة احتيال وعادية. معلن "تدريب" بكل رد، صفر اتصال بقاعدة البيانات، والتقييم من بايثون مو من النموذج اللغوي — عشان التعليم ما يمس أي قرار أو بيانات حقيقية. | `src/agents/training.py` + `docs/t12_training_ar.md` + صندوق "وضع تدريب" بـ `web/index.html` + `tests/test_training.py` | متوسط |
| 13 | شلون تقنعونا إن هاي مشكلة حقيقية وسمعتم أصحابها؟ | المشكلة موثقة من مصدرها (رسائل OTP، جائزة برسوم "معالجة"، طلب نقل لحساب "آمن") — والمطلوب من اللجنة دليل إنك **سألت أشخاص**: مقابلات مستخدمين بأسئلة جاهزة (3–5 أشخاص) موثقة بتاريخ ونص حرفي بملف مستقل. | `docs/user_research.md` (المقابلات) + `docs/project_summary_ar.md` + `ROADMAP.md` (وصف الهدف) | عالية |
| 14 | ليش بايثون وقواعد مو معمارية معقدة (RAG/Vector DB/ناقلات وكلاء)؟ | لأن الملف يقول: "Simple and reliable beats complex." القرار لازم يكون شفافاً وسريعاً ويعمل بدون إنترنت — قواعد بايثون تُقرأ بعين وتُراجع. ما فيه مستندات تُسترجع عشان نحتاج RAG، والأدوات كلها مبررة ومقيدة بـ `ROADMAP.md` وملف الإفصاح. | `ROADMAP.md` (القرارات المعمارية الثابتة) + `docs/DISCLOSURE.md` + بنية `src/` | متوسط |
| 15 | شنو اللي يثبت إنو يشتغل أمام إدخالنا نحن (اللجنة) مو أمام سيناريو محضّر؟ | التشغيل الحي: `/api/assess` يقبل JSON من اختياركم، `/api/scenario_text` يقبل نص حر باللهجة، والسيناريوهات الستة قابلة للتعديل. وأمامكم أداة `python -m src.demo_check` تفحص ست نقاط شاملة (قاعدة، 294 اختبار، مفتاح، اتصال النموذج، fallback، السيناريوهات). | `/docs` (OpenAPI) + `src/demo_check.py` + `demo/QA.md` + `demo/*.json` | عالية |

---

## 10. ملاحظات مهمة (Notes)

1. **شنو معنى "Stretch" بملف التحدي:** هو بند اختياري غير إلزامي، يُنجز "إذا بقي وقت" — نص الملف: "Stretch, if you have time: A training mode that simulates a scam attempt so a user can practise recognising one safely." تنفيذه يرفع التقييم، وعدم تنفيذه لا يستبعده وحده.

2. **وصف المشكلة والحل (صفحة موضوع 01):** الملف يسبق المتطلبات بوصف "The problem" و"What you build" — ووصف الحل المطلوب حرفي: "An agent with two layers. A detection layer watches transaction activity for known risk signals... A coaching layer steps in before the transaction completes and talks to the user in Iraqi Arabic: what looks wrong, why, and what a scammer would typically say next. The user can proceed or cancel. Every intervention and outcome is logged." — هذي ليست بنود تحقق منفصلة، لكنها مرجع الجواب "شنو تبنون بالضبط".

3. **غموض: شكل إدخال اللجنة** — عبارة "judge-supplied input" ما تحدد شكل الإدخال (JSON؟ نص؟ ملف؟). التفسير المعتمد: أي إدخال يلصقه الحكم لازم يشتغل — عشان كذا النظام يدعم الطريقتين: JSON منظّم (`/api/assess`) ونص حر بالدارجة (`/api/scenario_text`).

4. **غموض: مدة فترة البناء** — "commit history spanning the build period" ما لها تواريخ رسمية بالملف. التفسير: سجل الـ commits يجب أن **يمتد** على أيام/أسابيع البناء (متصل)، مو كلها بتاريخ واحد قبل التسليم.

5. **غموض: "evidence you spoke to someone"** — يعني مقابلات حقيقية بأقوال فعلية، مو آراء افتراضية مكتوبة. المطلوب: 3–5 أشخاص على الأقل كدليل، والأمثلة الحرفة تُحفظ بـ `docs/user_research.md`.

6. **غموض: "check a sample by hand"** — المراجعة اليدوية لازم تكون **موثقة** (كتابتها بملف)، مو مجرّد نظرتها — مكانها `docs/data_review.md` مع جدول المراجعة.

7. **الملف موسوم مسودة:** "DRAFT FOR REVIEW | 17/09/2026" — أي تحديث تنشره اللجنة له الأولوية على هذا المرجع. راجعي مصدر Topic_Briefs قبل يوم التسليم.

8. **الحدود الدنيا بملف موضوع 01:** "at least 20 users" للبيانات، و"At least three" لحالات الفشل. تجاوز الحد مسموح ومحتسب لصالحك، والنقص استبعاد.

9. **تنبيه `.env`:** اسم النموذج المكتوب هناك لازم يكون الاسم الفعلي الصحيح المتاح (مثل `gemini-3.6-flash`) — وإلا يفشل فحص `api_key` بـ `demo_check`. ولا ترفعين ملف `.env` أبداً مع المستودع (لازم يكون بـ `.gitignore`).

10. **تفسير "خارج النطاق":** يعني ما تبنيه كميزة وما تدّعي إتقانه — لا يعني حذف الملفات القائمة. الممنوع تحديداً بنداً واحداً: قفل التنفيذ بدون موافقة المستخدم، وتحويل الكشف للنموذج اللغوي.

11. **الملف يضم 6 مواضيع** (الصفحات 4–8 لمواضيع 02–06) وموضوعنا هو 01 وحده. عناوين المواضيع الستة من الصفحة الأولى: `01 Fraud & Scam Protection Agent` / `02 SME & Merchant Assistant` / `03 AI Loan Officer` / `04 Bill Pay & Transfer Agent` / `05 KYC Document Agent` / `06 Support Pipeline Automation` — وباقي المواضيع لا تنطبق علينا.

---

## كيفية استخدام هذا الملف

1. **للمستخدمة:** هذا الملف مرجعي. افتحيه عندما تحتاجين تعرفين شنو مطلوب. لا تعدّليه.
2. **لـ AI:** اقرأ هذا الملف كخريطة للمتطلبات، وقارن المشروع الحالي به لتحديد الفجوات.
3. **للجنة:** هذا الملف مرآة لمتطلبات التحدي الرسمي، وُضع للتأكد من الالتزام الكامل.
