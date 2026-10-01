# ملخص الوضع الحالي

## المشروع
مشروع **Fraud & Scam Protection Agent** لمحفظة موبايل بالعراق — قبل اكتمال التحويل، النظام يقيّمها وإذا مريبة يوقف الشاشة ويشرح للمستخدمة بلهجة عراقية.

## الـ Git
- 5 commits، آخرها: `45c7745 add AGENTS.md guidelines`
- commits السابقة تبين إن المهام T0–T4 مكتملة

## الاختبارات
- **134 اختبار ينجح**، 0 يفشل
- تحذير واحد فقط (Starlette deprecation — مو خطير)

## هيكل المشروع
| المجلد | المحتوى |
|--------|---------|
| `src/` | `api/`, `coaching/`, `detection/`, `eval/`, `generator/` + `config.py`, `db.py`, `models.py` |
| `tests/` | 8 ملفات اختبار (API, catalogue, coaching, engine, eval, features, rules, text_norm) |
| `docs/` | `eval_results.json` فقط — **ما فيه `PROGRESS.md`** (هذا من مخرجات T0) |
| `data/` | `synthetic/`, `test_sealed/` (معزول), `fraud.db`, `scam_catalogue.json` |
| `web/` | **فاضي** — الواجهة ما بدأت (T5) |

## الـ ROADMAP
- ✅ **T0–T4 مكتملة:** مواءمة الوثائق، رسائل التوعية، ربط Gemini، توليد البيانات بالـ LLM، مراجعة التقييم وضبط القواعد
- ⏭️ **التالية: T5 — الواجهة (`web/`)** — شاشة تشبه محفظة موبايل، RTL، بدون CDN

## التقنية
Python 3.14 / FastAPI / SQLite / pandas — الواجهة HTML+CSS+JS عادي بدون frameworks.
