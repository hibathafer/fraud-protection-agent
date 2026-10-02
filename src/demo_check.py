"""فحص جاهزية الديمو والتسليم (T10) — PASS/FAIL بالإنجليزي لكل بند.

التشغيل اليدوي (من جذر المشروع):
    python -m src.demo_check

البنود حسب ROADMAP T10: قاعدة البيانات، الاختبارات، وجود المفتاح، اتصال
Gemini (ووقت الاستجابة)، الـ fallback، وتحميل سيناريوهات demo/.
الناتج: exit code 0 إذا كلها PASS، و1 إذا في FAIL.

ملاحظتان مهمتان:
- بنود `api_key` و`gemini_connection` تنجح فقط إذا شغّلتي الوضع الذكي:
  `COACH_MODE=llm` بـ .env (أو بالبيئة) + مفتاح `GEMINI_API_KEY`.
  بدونها يرجع الرسالة للقالب دائماً — وهذا مو خلل، بس الديمو الحقيقي
  يبي المفتاح حتى تبان صياغة الـ LLM الحيّة.
- بنود الاختبارات تشغّل pytest فعلياً (بدون أي استدعاء LLM — الاختبارات
  mock حصراً بفضل tests/conftest.py).
"""

import json
import os
import subprocess
import sys
import time

from src import config
from src.coaching import llm
from src.coaching.coach import clear_cache, coach
from src.config import ROOT

DEMO_DIR = ROOT / "demo"
MIN_DEMO_SCENARIOS = 6

# مدخل فحص Gemini: جملة القالب بدون أي أرقام (تبقى صالحة بعد validators)
_GEMINI_PING_SOURCE = (
    "هاي أول مرة تحوّل لهذا الشخص، والمبلغ كبير على عادة. لا تعطي الرمز لأي أحد."
)

# assessment صغير لفحص الرجوع للقالب (رسالة التوعية هنا بدون LLM)
_FALLBACK_ASSESSMENT = {
    "score": 70,
    "raw_score": 70,
    "decision": "hold",
    "reasons": [
        {"rule_id": "NEW_RECIPIENT", "points": 20,
         "text_ar": "أول مرة تحوّل لهذا الشخص"}
    ],
    "matched_pattern": None,
    "pattern": None,
    "rules_version": config.RULES_VERSION,
}


def _line(name: str, ok: bool, detail: str = "") -> bool:
    """يطبع سطر PASS/FAIL واحد ويرجع هل النجح."""
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" - {detail}" if detail else ""))
    return bool(ok)


# ----------------------------------------------------------------- البنود
def check_database(client) -> tuple:
    """قاعدة البيانات: التطبيق يقحم ويرمّل dev وقت الإقلاع (lifespan)."""
    res = client.get("/api/users")
    data = res.json() if res.status_code == 200 else {}
    n_users = data.get("count", 0)
    return res.status_code == 200 and n_users > 0, f"users={n_users}"


def _run_pytest() -> tuple:
    """يشغّل pytest كامل كعملية فرعية (بدون LLM — mock حصراً)."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=900,
    )
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        err = [ln.strip() for ln in (proc.stderr or "").splitlines() if ln.strip()]
        lines = err or ["no output"]
    return proc.returncode == 0, lines[-1]


def check_tests(runner=None) -> tuple:
    """كل الاختبارات لازم تنجح (runner قابل للحقن بالاختبارات)."""
    ok, tail = (runner or _run_pytest)()
    return ok, tail


def check_api_key() -> tuple:
    """وجود المفتاح (ووضع التشغيل والنموذج المستعمل — تفاصيل للشفافية)."""
    mode = config.coach_mode()
    key = llm.load_api_key()
    detail = f"mode={mode} model={config.LLM_MODEL} key={'present' if key else 'missing'}"
    return key is not None, detail


def _ping_model(api_key: str) -> str:
    """استدعاء حقيقي واحد لـ Gemini — يرمي Exception عند أي مشكلة.

    منفصل عن llm.rewrite حتى يعرض demo_check سبب الفشل الحقيقي
    (503، اسم موديل غلط، شبكة...) بدل رسالة عامة.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_S * 1000)),
    )
    response = client.models.generate_content(
        model=config.LLM_MODEL,
        contents=_GEMINI_PING_SOURCE,
        config=types.GenerateContentConfig(
            system_instruction="تكتب بلهجة عراقية بسيطة ومحترمة بدون تهويل.",
            temperature=0.3,
            max_output_tokens=200,
        ),
    )
    return str(getattr(response, "text", None) or "").strip()


def _short(message: str, limit: int = 120) -> str:
    return " ".join(str(message).split())[:limit]


def check_gemini_connection() -> tuple:
    """استدعاء حيّ واحد لـ Gemini وقياس زمن الاستجابة (بالمفتاح الحقيقي)."""
    if config.coach_mode() == "template":
        return False, "COACH_MODE=template - set COACH_MODE=llm in .env"
    if not llm.enabled():
        return False, "GEMINI_API_KEY missing in .env"
    started = time.perf_counter()
    try:
        reply = _ping_model(llm.load_api_key())
    except Exception as exc:  # نعرض السبب الحقيقي (اسم موديل/شبكة/503...)
        latency_ms = round((time.perf_counter() - started) * 1000)
        message = str(exc)
        if llm.load_api_key():  # ما نعرض المفتاح أبداً لو تسرب برسالة الخطأ
            message = message.replace(llm.load_api_key(), "***")
        return False, (
            f"error={type(exc).__name__}: {_short(message)} (latency={latency_ms}ms)"
        )
    latency_ms = round((time.perf_counter() - started) * 1000)
    if not reply:
        return False, f"empty reply (latency={latency_ms}ms)"
    return True, f"model={config.LLM_MODEL} latency={latency_ms}ms"


def check_fallback() -> tuple:
    """فشل LLM (مهلة/خطأ/ناتج مرفوض) => الرجوع الفوري للقالب — بدون نت."""
    class _BrokenClient:
        def __init__(self):
            self.models = self

        def generate_content(self, **kwargs):
            raise RuntimeError("simulated outage")

    outage_falls_back = llm.rewrite(
        _GEMINI_PING_SOURCE, "أول مرة تحوّل لهذا الشخص", client=_BrokenClient()
    ) is None
    clear_cache()
    result = coach(_FALLBACK_ASSESSMENT, use_llm=False)
    clear_cache()
    template_ok = result.get("source") == "template" and bool(result.get("message"))
    return outage_falls_back and template_ok, "outage->template, use_llm=False->template"


def load_demo_files() -> tuple:
    """يقرأ ملفات demo/*.json ويتحقق من شكلها (بدون خادم)."""
    problems = []
    count = 0
    for path in sorted(DEMO_DIR.glob("*.json")):
        count += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        payload = data.get("payload")
        if not data.get("name_ar") or not isinstance(payload, dict):
            problems.append(f"{path.name}: missing name_ar or payload")
        elif not ({"user_id", "history", "text"} & set(payload)):
            problems.append(f"{path.name}: payload has no user_id/history/text")
    return count, problems


def check_demo_scenarios(client) -> tuple:
    """تحميل سيناريوهات demo/: الملفات + قائمة الـ endpoint نفسها."""
    count, problems = load_demo_files()
    res = client.get("/api/demo_scenarios")
    endpoint_count = res.json().get("count", -1) if res.status_code == 200 else -1
    ok = (
        count >= MIN_DEMO_SCENARIOS
        and endpoint_count == count
        and not problems
    )
    detail = f"files={count} endpoint={endpoint_count}"
    if problems:
        detail += f" problems={'; '.join(problems)}"
    return ok, detail


# ----------------------------------------------------------------- main
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    from fastapi.testclient import TestClient

    from src.api import main as api

    results = []
    # عميل واحد: الإقلاع يهيّئ القاعدة ويحمّل dev مرة وحدة
    with TestClient(api.app) as client:
        results.append(_line("database", *check_database(client)))
        results.append(_line("tests", *check_tests()))
        results.append(_line("api_key", *check_api_key()))
        results.append(_line("gemini_connection", *check_gemini_connection()))
        results.append(_line("fallback", *check_fallback()))
        results.append(_line("demo_scenarios", *check_demo_scenarios(client)))

    passed = sum(results)
    total = len(results)
    if all(results):
        print(f"ALL CHECKS PASSED ({passed}/{total})")
        return 0
    print(f"{total - passed} CHECKS FAILED ({passed}/{total})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
