"""الـ LLM اختياري: صياغة رسالة التوعية فقط (قسم 8.3 و8.4).

قواعد صارمة:
- ما يشوف score ولا القرار، ولا يغيّرهم. مدخله القالب + أسباب الكشف فقط.
- ما يشتغل إلا إذا LLM_ENABLED = True ومفتاح GEMINI_API_KEY موجود.
- أي خطأ أو تأخير أو ناتج مرفوض => يرجع None، وcoach.py يرجع للقالب.
"""

import os
import re

from src import config
from src.config import LLM_TIMEOUT_S, LLM_VALIDATION_MAX_WORDS

# استيراد google-genai و python-dotenv داخل الدالة حتى ما يتعطل المشروع بدونهم
_DOTENV_LOADED = False

_ARABIC = re.compile(r"[\u0600-\u06ff]")
_DIGITS = re.compile(r"[0-9\u0660-\u0669]+")
_LINKS = re.compile(
    r"(?:https?://|www\.)\S+|\S+@\S+|\S+\.(?:com|net|org|info|io|iq|ly)\b", re.IGNORECASE
)
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

PROMPT = (
    "إعادة صياغة الجملة التالية باللهجة العراقية العامية البسيطة.\n"
    "القواعد: لا تضيف أي معلومة جديدة، لا أرقام، لا روابط، لا أسماء. "
    f"أقصى طول {config.COACHING_MAX_WORDS} كلمة. رجّع الجملة فقط بدون أي شرح.\n"
    "الجملة:\n{text}"
)


def load_api_key():
    """يرجع المفتاح من البيئة أو من ملف .env، أو None."""
    global _DOTENV_LOADED
    if not _DOTENV_LOADED:
        _DOTENV_LOADED = True
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:  # python-dotenv اختياري: نكمل بدونه
            pass
    return os.environ.get("GEMINI_API_KEY") or None


def enabled() -> bool:
    """الـ LLM مفعّل فقط بالعلم في config.py (مطفي افتراضياً) + مفتاح موجود."""
    return bool(config.LLM_ENABLED) and load_api_key() is not None


def build_prompt(template_text: str, reasons_text: str = "") -> str:
    """المدخل المرسل للـ LLM: القالب + الأسباب، بدون score ولا قرار."""
    parts = [str(template_text or "").strip()]
    if reasons_text:
        parts.append("أسباب التنبيه: " + str(reasons_text).strip())
    return PROMPT.format(text="\n".join(parts))


def _numbers(text) -> list:
    """كل الأرقام بالمدخل/الناتج، بعد توحيد الأرقام العربية الهندية."""
    return [d.translate(_DIGIT_MAP) for d in _DIGITS.findall(str(text))]


def validate(text, source_text: str) -> bool:
    """يتفقّص ناتج الـ LLM قبل ما نستخدمه: عربي، بطول معقول، بدون أرقام أو روابط جديدة."""
    text = str(text or "").strip()
    source = str(source_text or "")
    if not text:
        return False
    if not _ARABIC.search(text):  # لازم عربي
        return False
    if len(text.split()) > LLM_VALIDATION_MAX_WORDS:  # حد الطول
        return False

    source_digits = set(_numbers(source))
    if any(d not in source_digits for d in _numbers(text)):
        return False  # رقم ما موجود بالمدخل = تلميح أو معلومة مختلقة

    source_links = {l.lower() for l in _LINKS.findall(source)}
    if any(l.lower() not in source_links for l in _LINKS.findall(text)):
        return False  # رابط جديد ما موجود بالمدخل

    return True


def _extract_text(response) -> str:
    """يسحب النص من ردّ google-genai بأكثر من شكل متوقع."""
    if response is None:
        return ""
    getter = getattr(response, "text", None)
    if isinstance(getter, str) and getter.strip():
        return getter
    for part in getattr(response, "parts", None) or []:
        value = getattr(part, "text", None)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def rewrite(template_text: str, reasons_text: str = "", client=None) -> str | None:
    """يعيد صياغة القالب. يرجع نص صالح، أو None إذا ما نقدر نستخدم الـ LLM.

    client: اختياري للاختبارات (أي شي عنده .models.generate_content).
    """
    if not enabled() and client is None:
        return None
    try:
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=load_api_key())
            response = client.models.generate_content(
                model=config.LLM_MODEL,
                contents=build_prompt(template_text, reasons_text),
                config=types.GenerateContentConfig(
                    system_instruction="تكتب بلهجة عراقية بسيطة ومحترمة بدون تهويل.",
                    temperature=0.3,
                    max_output_tokens=200,
                ),
                http_options=types.HttpOptions(timeout=int(LLM_TIMEOUT_S * 1000)),
            )
        else:
            response = client.models.generate_content(
                model=config.LLM_MODEL,
                contents=build_prompt(template_text, reasons_text),
            )
    except Exception:  # خطأ شبكة أو مهلة أو مفتاح غلط: نرجع للقالب
        return None

    text = _extract_text(response).strip()
    if not validate(text, template_text + " " + reasons_text):
        return None
    return text
