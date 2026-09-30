"""العتبات والأوزان والمسارات (قسم 3). كل الأرقام القابلة للضبط تجمع هنا."""

from datetime import date, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SYNTH_DIR = DATA_DIR / "synthetic"
SEALED_DIR = DATA_DIR / "test_sealed"
CATALOGUE_PATH = DATA_DIR / "scam_catalogue.json"
DB_PATH = DATA_DIR / "fraud.db"

SEED = 42
BAGHDAD_TZ = timezone(timedelta(hours=3))
END_DATE = date(2026, 10, 20)
RULES_VERSION = "v1"

# عتبات القرار (7.2)
WARN_SCORE = 30
HOLD_SCORE = 60
SCORE_MAX = 100

# أوزان القواعد (7.2)
POINTS = {
    "NEW_RECIPIENT": 20,
    "YOUNG_RECIPIENT_ACCOUNT": 15,
    "AMOUNT_HIGH": 25,
    "BALANCE_DRAIN": 15,
    "ODD_HOUR": 10,
    "RAPID_SEQUENCE": 15,
    "SCAM_PATTERN": 35,  # أو وزن النمط نفسه
    "CUMULATIVE_NEW_RECIPIENT": 20,
    "TRUSTED_RECIPIENT": -25,
}

# تفاصيل كل قاعدة
AMOUNT_HIGH_FACTOR = 3          # 3 × median
MIN_TX_FOR_PROFILE = 10         # أقل عدد معاملات قبل ما نستخدم العتبة الثابتة
AMOUNT_HIGH_FALLBACK = 300_000   # عتبة ثابتة إذا التاريخ قصير
YOUNG_ACCOUNT_DAYS = 14          # عمر حساب المستمل الجديد
DRAIN_RATIO = 0.7                # المبلغ >= 70% من الرصيد
ODD_HOURS = (0, 1, 2, 3, 4, 5)   # الساعات اللي نعدّها وقت غريب
TYPICAL_HOURS_SHARE = 0.05       # ساعة "مألوفة" إذا >= 5% من النشاط
RAPID_WINDOW_MINUTES = 30
RAPID_MIN_COUNT = 3              # 3 تحويلات (بضمن الحالية)
CUMULATIVE_DAYS = 7
CUMULATIVE_MIN_COUNT = 3         # 3 تحويلات لنفس المستلم الجديد
CUMULATIVE_SUM_FACTOR = 2        # مجموعها >= 2 × median
TRUSTED_MIN_COUNT = 3            # تحويلات سابقة
TRUSTED_MIN_SPAN_DAYS = 14       # بين أول وآخر تحويل

# طبقة التوعية (قسم 8): القوالب تشتغل دائماً، والـ LLM اختياري ومطفي افتراضياً
COACHING_MAX_WORDS = 60          # حد الكلمات بالقوالب (نفس حد الـ prompt)
LLM_ENABLED = False              # مطفي افتراضياً: المشروع يشتغل بدون نت
LLM_MODEL = "gemini-2.0-flash"
LLM_TIMEOUT_S = 4.0              # بعده نرجع للقالب
LLM_VALIDATION_MAX_WORDS = 70    # تسامح بسيط فوق حد الـ prompt
