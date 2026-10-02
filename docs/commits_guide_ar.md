# دليل الـ Commits — خطوة بخطوة (تعمليها إنتِ)

> افتحي هذا الملف بـ VS Code. القاعدة (AGENTS.md رقم 9): **الوكيل ما يعمل
> commit أبداً** — إنتِ تراجعين ثم تأكدين. هذا دليل جاهز تنسخين منه.

---

## أول شي: تأكيدات أمان (دقيقة وحدة)

افتحي PowerShell بمجلد المشروع وشغّلي:

```powershell
git status
```

- ✅ لازم **ما تشوفين** `.env` بقائمة الملفات (إذا ظهر = توقفي وقوليلي).
- ✅ المفروض تشوفين كثير ملفات معدّلة وجديدة (هذا شغل T5b → T12 كله بانتظارك).
- 🔑 تأكيد إضافية إنو ما بمكو مفاتيح:
  ```powershell
  git grep -I "AIza"    # لازم ما يرجّع شي
  ```

## الطريقة المختصرة (commit واحد شامل) ⭐

كل الشغل المختلط بملفات واحدة (`src/api/main.py` فيها T5b+T6+T11+T12) ما
ينفصل بسهولة — فالأمثل أنو **commit وحد شامل** لكل ما تراكم + commits منفصلة
من الحين فما بعد:

```powershell
git add -A
git commit -m "feat: T5b-T12 wallet flow, intake, failure modes, demo package, dialogue agent, training mode (294 tests)"
git push
```

## الطريقة المرتبة (5 commits — لو تحبين النظافة)

```powershell
# 1) الوكيل + المحفظة + الواجهة (T5b)
git add web/ src/integrations/ src/api/ src/models.py src/db.py
git commit -m "feat(T5b): Zain Cash wallet interception, hold-wait, receipts, UI"

# 2) النص الحر + حالات الفشل + أمان LLM (T6-T8)
git add src/agents/ src/eval/ docs/failure_modes.md docs/privacy_notes.md docs/llm_evaluation.md
git commit -m "feat(T6-T8): intake agent, failure modes, LLM safety eval"

# 3) الاختبار المعزول + التقييم (T9)
git add docs/evaluation_report.md docs/test_runs.log docs/eval_results.json
git commit -m "feat(T9): sealed evaluation run + report"

# 4) حزمة الديمو والتسليم (T10)
git add README.md demo/ docs/DISCLOSURE.md docs/data_review.md docs/user_research.md prompts/ .env.example src/demo_check.py src/config.py
git commit -m "feat(T10): demo package, disclosure, demo_check, COACH_MODE"

# 5) الحوار + التدريب + كل الوثائق (T11-T12 والتغييرات)
git add -A
git commit -m "feat(T11-T12): dialogue agent, training mode, docs refresh (294 tests)"
```

(أي خطوة تقول "ناقص ملف" عادي — كمّلي `git add <الملف>` قبل الـ commit.)

## بعد كل commit

```powershell
git push          # يرفع لحسابك بـ GitHub
git log --oneline -5   # يبيّن آخر 5 commits
```

## أسئلة شائعة

| السؤال | الجواب |
|--------|--------|
| غلطت برسالة الـ commit؟ | `git commit --amend -m "رسالة جديدة"` (فقط قبل ما ترفعين) |
| أبي أشوف شنو بالـ commit قبل؟ | `git show --stat` |
| ظهر `.env` بـ status؟ | **لا تضيفينه** — `git reset .env` وقوليلي |
| نسيت ملف؟ | عادي: commit ثانية `git add الملف && git commit -m "docs: ..."`.
