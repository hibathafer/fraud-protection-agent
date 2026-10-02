"""إعداد وضع التوعية COACH_MODE (T10): template | llm | auto.

الملف يقرأ من البيئة أو من .env — الاختبارات هنا تضبط متغيّر البيئة بس
(متغيّر البيئة يغلب على أي قيمة بالـ .env، فتكون النتائج حتمية).
"""

from src import config


def test_llm_mode_enables_llm_path(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "llm")
    assert config.coach_mode() == "llm"
    assert config._mode_enables_llm(config.coach_mode()) is True


def test_auto_mode_enables_llm_path(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "auto")
    assert config.coach_mode() == "auto"
    assert config._mode_enables_llm(config.coach_mode()) is True


def test_template_mode_keeps_templates_only(monkeypatch):
    monkeypatch.setenv("COACH_MODE", "template")
    assert config.coach_mode() == "template"
    assert config._mode_enables_llm(config.coach_mode()) is False


def test_unknown_mode_falls_back_to_template(monkeypatch):
    """قيمة غريبة = القالب (آمن: بدون LLM بدون مفاجآت)."""
    monkeypatch.setenv("COACH_MODE", "banana")
    assert config.coach_mode() == "template"
    assert config._mode_enables_llm(config.coach_mode()) is False


def test_setting_reads_env_before_dotenv(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-1")
    assert config._setting("GEMINI_MODEL", "fallback") == "gemini-test-1"


def test_model_setting_is_a_nonempty_string():
    """LLM_MODEL يُقرأ وقت الاستيراد: لازم نص فارغ الاسم (gemeni أو env)."""
    assert isinstance(config.LLM_MODEL, str)
    assert config.LLM_MODEL.strip()
