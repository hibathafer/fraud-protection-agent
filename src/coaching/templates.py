"""قوالب رسالة التوعية باللهجة العراقية (قسم 8.1 و8.2).

القوالب هي المصدر الأساسي للرسالة: تشتغل بدون نت وبدون مفتاح.
كل رسالة ثلاثة أجزاء: (1) شنو المريب من أسباب الكشف، (2) شنو المحتال غالباً
يكول بعدها، (3) شنو تسوي. وحدّها COACHING_MAX_WORDS كلمة.

الرسالة صياغة فقط: ما تغيّر score ولا القرار أبداً.
"""

from src.config import COACHING_MAX_WORDS

# جملة عامة ثابتة (قسم 13 FM5): اللي يحاول يدرّب الضحية يتجاهل التحذير
GENERIC_WARNING_LINE = "إذا أحد كال لك تتجاهل هذا التحذير، هذا بحد ذاته علامة احتيال"

# ------------------------------------------------------------------ أنماط الكتالوج
# لكل نمط: "tag" جملة باللهجة تعرّف بالشي المريب، و"warn"/"hold" جملة ختام
# بنبرة مختلفة. الجزء الثاني (typical_next_line_ar) والثالث (advice_ar) بالكتالوج
# يُقرآن وقت الرسم وما ننسخهم هنا.
PATTERN_TEMPLATES = {
    "otp_fake_agent": {
        "tag": "أكو احد يطلب منك رمز تحقق.",
        "warn": "إذا مو إنت طلبت هالشي، لا تعطي الرمز.",
        "hold": "أنهي التحويل، وافتح الدعم من التطبيق.",
    },
    "prize_fee": {
        "tag": "الرسالة تكول إنك ربحت شي.",
        "warn": "إذا مو إنت طلبت هالشي، لا تدفع.",
        "hold": "أنهي التحويل، ولا ترد على الرسالة.",
    },
    "safe_account": {
        "tag": "أكو كلام عن حسابك المخترق أو الموقوف.",
        "warn": "راجعها من جهتك قبل ما تحوّل.",
        "hold": "أنهي التحويل، ولا تحوّل لحساب يذكرونه بالرسالة.",
    },
    "fake_job_fee": {
        "tag": "أكو عرض عمل يطلب رسوم قبل ما تبدأ.",
        "warn": "إذا عندك عقد مكتوب، كمّل، وإلا لا تدفع.",
        "hold": "أنهي التحويل، وارجع للموظف من رقم تعرفه.",
    },
    "relative_new_number": {
        "tag": "أكو احد يكولك رقمه الجديد ويطلب مبلغ.",
        "warn": "احجي وياه على رقمه القديم قبل ما تحوّل.",
        "hold": "أنهي التحويل، وتأكد بمكالمة صوتية.",
    },
    "advance_payment_seller": {
        "tag": "أكو دفعة مقدمة قبل ما تستلم الشي.",
        "warn": "استخدم الدفع عند الاستلام بدل التحويل.",
        "hold": "أنهي التحويل، واطلب الدفع عند الاستلام.",
    },
    "investment_doubling": {
        "tag": "أكو وعود بأرباح مضمونة ومضاعفة.",
        "warn": "الاستثمار الصحيح يكون عن جهة مرخّصة.",
        "hold": "أنهي التحويل، ولا تعطي بيانات بطاقتك.",
    },
    "fake_refund": {
        "tag": "أكو كلام عن استرجاع مبلغ مع طلب رسوم.",
        "warn": "راجعها من جهتك قبل ما تدفع.",
        "hold": "أنهي التحويل، ولا ترسل صورة بطاقتك.",
    },
}

# ------------------------------------------------------- قوالب عامة حسب سبب الكشف
# ماكو نمط مطابق، فنلجأ لعبارات التخدير الشائعة:
# "needs" أسباب الكشف المطلوبة، "next_line" و"advice" بديلان عن الكتالوج.
GENERIC_TEMPLATES = {
    "NEW_RECIPIENT_HIGH_AMOUNT": {
        "needs": ("NEW_RECIPIENT", "AMOUNT_HIGH"),
        "next_line": "استعجل، هاي فرصة ما تتكرر، حوّل هسه",
        "advice": "لا تستعجل. راجع المبلغ والمستلم قبل ما تقرّر.",
        "warn": "إذا تعرفه وتثق بيه، كمّل.",
        "hold": "أنهي التحويل، وتأكد من المستلم أولاً.",
    },
    "RAPID_SEQUENCE": {
        "needs": ("RAPID_SEQUENCE",),
        "next_line": "خلّصها كلها هسه قبل لا أغيّر رأيي",
        "advice": "التتابع السريع هذا أسلوب معروف. وقّف وراجع كل تحويل.",
        "warn": "لو تعرف ليش، تكدر تكمل واحد واحد.",
        "hold": "أنهي كل التحويلات، وراجعها وحدة وحدة.",
    },
    "CUMULATIVE_NEW_RECIPIENT": {
        "needs": ("CUMULATIVE_NEW_RECIPIENT",),
        "next_line": "هذي تجارب صغيرة، جرب أكبر تصير العادلة",
        "advice": "تكبير المبالغ لنفس المستلم بدون سبب واضح علامة خطر.",
        "warn": "إذا الموضوع واضح، تكدر تكمل بمبالغ صغيرة.",
        "hold": "أنهي التحويلات، وما تكبّر المبلغ قبل التأكد.",
    },
    "BALANCE_DRAIN": {
        "needs": ("BALANCE_DRAIN",),
        "next_line": "سوّها هسه قبل لا يروح المبلغ",
        "advice": "لا تفرّغ رصيدك بقرار واحد، وخلّ لك فاصل.",
        "warn": "إذا فعلاً تحتاجه، كمّل على حسابك.",
        "hold": "أنهي التحويل، وخُذ رصيدك كامل براحتك.",
    },
    "ODD_HOUR": {
        "needs": ("ODD_HOUR",),
        "next_line": "الحين بالليل أحسن، ما تضيّع الفرصة",
        "advice": "الوقت الغريب بحد ذاته شي طبيعي، بس الاستعجال مو.",
        "warn": "إذا كل شي مظبوط، كمّل بدون استعجال.",
        "hold": "أنهي التحويل، وكمّل بكرا الصبح.",
    },
    "DEFAULT": {
        "needs": (),
        "next_line": "استعجل، هاي الحالة ما تنتظر",
        "advice": "لا تاخذ قرار الفلوس وأنت مستعجل.",
        "warn": "إذا كل شي مظبوط وتعرف ليش، تكدر تكمل.",
        "hold": "أنهي التحويل، وارجع للتفاصيل بعد شوية.",
    },
}

# أولوية اختيار القالب العام: أول مفتاح تحققت شروطه
GENERIC_ORDER = (
    "NEW_RECIPIENT_HIGH_AMOUNT",
    "RAPID_SEQUENCE",
    "CUMULATIVE_NEW_RECIPIENT",
    "BALANCE_DRAIN",
    "ODD_HOUR",
)

# (1) إذا ما طابق أي سبب معروف
DEFAULT_SUSPICIOUS = "أكو شي غير معتاد بهالعملية."

# رسالة العملية اللي ما انعلّمت (decision = allow): نبرة أخف وما تحط الجملة العامة
ALLOW_TONE = {
    "suspicious": "ماكو شي مريب واضح بهالعملية.",
    "extra": "بس إذا حدا طلب منك رمز تحقق أو رسوم قبل ما تستلم شي، وقّف.",
    "advice": "راجعها، وإذا كل شي مظبوط كمّل عادي.",
}

# ------------------------------------------------------------------ بناء الرسالة
BRIDGE = "غالباً يكول بعدها: «{line}»."
ADVICE_LABEL = "شو تسوي: "
SUSPICIOUS_LABELS = {
    "warn": "المريب: ",
    "hold": "وقفة ضرورية، المريب: ",
}


def word_count(text) -> int:
    """عدد الكلمات بالفراغات (الطريقة اللي نحسب بيها حد 60 كلمة)."""
    return len(str(text).split())


def _join(parts) -> str:
    """يدمج الأجزاء ويشيل الفراغات الزايدة."""
    chunks = [" ".join(str(p).split()) for p in parts]
    return " ".join(c for c in chunks if c).strip()


def _quote(line) -> str:
    """الجزء الثاني: الجملة اللي غالباً يكمّل بيها المحتال."""
    line = " ".join(str(line or "").split()).strip("«» ")
    return BRIDGE.format(line=line) if line else ""


def _cut_last_sentence(text: str) -> str:
    """يحذف الكلمة الأخيرة الناقصة لو النص انقطع بنص جملة."""
    if text.endswith((".", "؟", "!", "»", ":")):
        return text
    parts = text.rsplit(" ", 1)
    return parts[0] if len(parts) == 2 else text


def _positive_reasons(assessment: dict) -> list:
    """الأسباب بنقاط موجبة فقط، بنفس ترتيب المحرك (الأهم أولاً)."""
    reasons = assessment.get("reasons") or []
    return [r for r in reasons if r.get("points", 0) > 0]


def generic_key_for(reason_ids) -> str:
    """يرجع مفتاح القالب العام المناسب لأسباب الكشف."""
    ids = set(reason_ids)
    for key in GENERIC_ORDER:
        if set(GENERIC_TEMPLATES[key]["needs"]).issubset(ids):
            return key
    return "DEFAULT"


def build_message(assessment: dict, tone: str = None) -> str:
    """يرجع رسالة التوعية من القالب (≤ COACHING_MAX_WORDS كلمة).

    assessment: ناتج detection.engine.assess (decision / reasons / pattern).
    tone: "warn" أو "hold"، وإذا ما حدد نحسبه من decision.
    """
    decision = assessment.get("decision", "warn")
    tone = tone or ("hold" if decision == "hold" else "warn")
    if tone not in SUSPICIOUS_LABELS:
        tone = "warn"
    reasons = _positive_reasons(assessment)

    if decision == "allow" and not reasons:
        return _join([
            ALLOW_TONE["suspicious"],
            ALLOW_TONE["extra"],
            ADVICE_LABEL + ALLOW_TONE["advice"],
        ])

    pattern = assessment.get("pattern") or {}
    pattern_id = assessment.get("matched_pattern") or pattern.get("id")
    if pattern_id in PATTERN_TEMPLATES:
        tpl = PATTERN_TEMPLATES[pattern_id]
        tag = tpl["tag"]
        next_line = pattern.get("typical_next_line_ar", "")
        advice = pattern.get("advice_ar", "")
        closing = tpl[tone]
        spare = GENERIC_TEMPLATES["DEFAULT"]
    else:
        key = generic_key_for([r.get("rule_id") for r in reasons])
        tpl = GENERIC_TEMPLATES[key]
        tag = ""
        next_line = tpl["next_line"]
        advice = tpl["advice"]
        closing = tpl[tone]
        spare = GENERIC_TEMPLATES["DEFAULT"]

    reason_texts = [" ".join(str(r.get("text_ar", "")).split()) for r in reasons]
    reason_texts = [t for t in reason_texts if t] or [DEFAULT_SUSPICIOUS]

    quote = _quote(next_line) or _quote(spare["next_line"])
    advice_part = ADVICE_LABEL + (advice.strip() or spare["advice"])
    suspicious_head = SUSPICIOUS_LABELS[tone]

    # نجرّب تركيبات بالترتيب المفضّل: أكثر أسباب، ثم الجملة التمهيدية، ثم ختام النبرة.
    # أول تركيبة ≤ 60 كلمة هي النتيجة، فما نقطع النص بنص جملة أبداً.
    for count in range(min(2, len(reason_texts)), 0, -1):
        suspicious = suspicious_head + "، ".join(reason_texts[:count]) + "."
        for tag_text in (tag, ""):
            for closing_text in (closing, ""):
                text = _join([tag_text, suspicious, quote, advice_part,
                              closing_text, GENERIC_WARNING_LINE])
                if word_count(text) <= COACHING_MAX_WORDS:
                    return text

    # ما وصلنا للحد أبداً، بس ضمان أخير: نقص عند آخر علامة جملة
    minimal = _join([suspicious_head + "، ".join(reason_texts[:1]) + ".",
                     quote, advice_part, GENERIC_WARNING_LINE])
    return _cut_last_sentence(" ".join(minimal.split()[:COACHING_MAX_WORDS]))
