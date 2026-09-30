"""مولّد البيانات الاصطناعية (قسم 6).

- 30 مستخدم (20 dev + 10 test، التقسيم حسب المستخدم مو حسب المعاملة)
- كل مستخدم 60–120 يوم سجل بمعدل 1–3 معاملات باليوم تقريباً
- 60% تحويل لجهة اتصال معروفة، 20% فواتير، 15% تاجر، 5% مستلم جديد بريء
- حالات بريئة صعبة (6.4) + سيناريوهات احتيال مزروعة للـ 8 أنماط (6.5)
- random.seed(42) دائماً حتى تتكرر النتائج

التشغيل:  python -m src.generator.generate_data
"""

import csv
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from src.config import SEED, SYNTH_DIR, SEALED_DIR, BAGHDAD_TZ, END_DATE, ROOT
from src.detection.rules import load_catalogue, match_catalogue

USER_COLUMNS = ["user_id", "name", "archetype", "split"]
TX_COLUMNS = [
    "tx_id", "user_id", "ts", "amount_iqd", "balance_before_iqd", "tx_type",
    "recipient_id", "recipient_age_days", "note", "context_message",
    "is_scam", "scam_type", "case_id",
]

# ---------------------------------------------------------------- أنماط المستخدمين (6.2)
ARCHETYPES = {
    "salaried": {
        "label_ar": "موظف براتب",
        "contacts": (6, 12),
        "transfer": (50_000, 400_000),
        "bill": (25_000, 150_000),
        "merchant": (20_000, 200_000),
        "hours": tuple(range(8, 19)),
        "start_balance": (4_000_000, 9_000_000),
        "income": (1_800_000, 2_200_000),
        "income_days": (1, 15),
    },
    "student": {
        "label_ar": "طالب",
        "contacts": (5, 10),
        "transfer": (5_000, 60_000),
        "bill": (10_000, 60_000),
        "merchant": (8_000, 70_000),
        "hours": tuple(range(12, 24)),
        "start_balance": (400_000, 1_500_000),
        "income": (250_000, 400_000),
        "income_days": (10, 25),
    },
    "small_business": {
        "label_ar": "تاجر صغير",
        "contacts": (8, 15),
        "transfer": (100_000, 1_200_000),
        "bill": (50_000, 400_000),
        "merchant": (30_000, 400_000),
        "hours": tuple(range(19, 24)) + (0, 1, 2, 3),
        "start_balance": (3_000_000, 12_000_000),
        "income": (1_200_000, 3_000_000),
        "income_days": (3, 12, 24),
    },
    "family_supporter": {
        "label_ar": "معيل عائلة",
        "contacts": (7, 14),
        "transfer": (75_000, 700_000),
        "bill": (40_000, 250_000),
        "merchant": (25_000, 300_000),
        "hours": tuple(range(9, 23)),
        "start_balance": (3_000_000, 10_000_000),
        "income": (2_000_000, 2_600_000),
        "income_days": (1, 15),
    },
    "night_owl": {
        "label_ar": "سهران",
        "contacts": (5, 11),
        "transfer": (20_000, 250_000),
        "bill": (20_000, 120_000),
        "merchant": (10_000, 150_000),
        "hours": (0, 1, 2, 3, 4, 18, 19, 20, 21, 22, 23),
        "start_balance": (1_500_000, 5_000_000),
        "income": (900_000, 1_600_000),
        "income_days": (5, 18),
    },
}

NAMES = [
    "أحمد كامل", "زينب حسن", "مصطفى عباس", "نور الهدى", "كرار جبار", "مريم سالم",
    "علي جاسم", "رند عدنان", "ياسر خليل", "هدى حميد", "حيدر نوري", "سارة فاضل",
    "حسين قاسم", "مروة ليث", "عمر كرار", "زينب علي", "أوس داود", "رؤى صالح",
    "باقر كاظم", "نور عبد", "محمد رضا", "سجاد علي", "تبارك حسن", "مريم غازي",
    "علاء صادق", "هدى جبار", "مصطفى نوري", "رنا فاضل", "كرار خضير", "أم أحمد",
]

# ---------------------------------------------------------------- نصوص المعاملات الطبيعية
BILL_NOTES = [
    "فاتورة الكهرباء", "فاتورة الماء", "فاتورة الهاتف", "تجديد الاشتراك",
    "فاتورة التأمين", "دفع القسط", "رسوم الاشتراك",
]
MERCHANT_NOTES = [
    "شراء من السوق", "تموين البيت", "أدوات مدرسية", "قطع غيار",
    "غداء", "غسيل وكيّاسة", "دواء", "قطع غيار السيارة", "مستلزمات منزلية",
]
TRANSFER_NOTES = [
    "على الحساب", "دين قديم", "حصة الأرض", "دين لأخي", "مبلغ أمانة",
    "رد مبلغ", "تسديد دين", None, None,
]
NEW_RECIPIENT_NOTES = [
    "أول تحويل", "دفعة أولى", "تسديد حساب", "مبلغ تعاون", "دفعة أولى للمشروع",
    "أول راتب", None,
]

# ---------------------------------------------------------------- نصوص الاحتيال (6.5)
# "keyword" صياغات تطلع مع كتالوج الأنماط، "silent" بدون كلمات مفتاحية
# (نقطة ضعف موثقة). لكل نمط صياغات مختلفة حتى ما يصير التقييم كذبة.
SCAM_TEXTS = {
    "otp_fake_agent": {
        "keyword": [
            "موظف الدعم يطلب رمز تحقق منك، بعده يفعّل الحساب",
            "هسه لازم تعطيني الكود ورمز التحقق بدون تأخير",
            "أرسل الكود من صفحة التحقق وراح يفعّلوا حسابك",
            "OTP Timeout 30 ثانية، بدون الكود ما يگبل الحساب",
            "عميلنا الكرام، سيتم إيقاف الحساب، أرسل رمز التحقق",
            "لازم تفعّل الحساب، موظف الدعم ينتظر رمز التحقق",
        ],
        "silent": [
            "الحساب يحتاج خطوة ثانية، ساعدني أكملها",
            "لازم أگبل خطوة التأكيد حتى أتابع",
            "نسيت الخطوة الثانية، ساعدني",
            "حسابي، شنو الخطوة اللي بعدين؟",
            "تمام، شنو المطلوب مني الحين؟",
        ],
    },
    "prize_fee": {
        "keyword": [
            "مبروك ربحت الجائزة، حول رسوم المعالجة ونرسل لك المكافأة",
            "شكرا لمشاركتك، فزت بسحب المحفظة، ادفع رسوم التوصيل",
            "وصلتك المجموعة الواردة ثلاثة مليون، ادفع رسوم الاستلام حتى نصرفها",
            "ربحت جائزة، حوّل رسوم المعالجة والحساب يوصلها طول",
            "هدية من المحفظة، ادفع رسوم الاستلام تستلم الجائزة",
            "راسلتك شركة المحفظة، ادفع رسوم المعالجة وربحت الجائزة",
        ],
        "silent": [
            "هاي أول مرة نحچي بيه، حول مبلغ وبعدها نكمل",
            "خلّينا نكمل الموضوع من الأمس",
            "وصلني شي، شنو الخطوة الجاية؟",
            "وصلتني رسالة، خلّيني أچيك بالتفاصيل",
            "عندي خبر حلو، بعدين احچيك",
        ],
    },
    "safe_account": {
        "keyword": [
            "حسابك مخترق، حوّل المبلغ لحساب أمان، بعدها نرجّعه",
            "تم اختراق حسابك، سجّل دخولك بحساب أمان جديد",
            "الحساب موقوف، حوّل لحساب آمن حتى نكمل الإجراء",
            "لازم نسوي إنشاء حساب جديد، بعدها سجل دخولك يشتغل",
            "خطأ بالحساب، سجّل دخولك بحساب أمان جديد",
        ],
        "silent": [
            "حسابي ما يشتغل، ساعدني خطوة؟",
            "لازم أغير الإعدادات تبع حسابي",
            "صار عندي مشكلة ب الدخول، شنو الحل؟",
            "ما أعرف شنو نسوي، وين أروح؟",
            "خلّيني أساعدج خطوة خطوة",
        ],
    },
    "fake_job_fee": {
        "keyword": [
            "وظيفة جديدة، تدفع رسوم التسجيل وبعدها التقديم ينجح",
            "عندك عرض عمل، تدفع رسوم التقديم وتدخل مرحلة التوظيف",
            "الراتب مضمون، بس ادفع رسوم التسجيل قبل ما نوثق العقد",
            "وظائف عن بعد، تسجيل قبل البدء مطلوب",
            "تعيين لوظيفة، رسوم التسجيل شرط قبل التعيين",
        ],
        "silent": [
            "أريد أرسل السيرة الذاتية، من وين أبدأ؟",
            "شنو الورق المطلوبة؟",
            "شلون أبدأ هسه؟",
            "من وين نبدأ بالتفصيل؟",
            "ممتاز، شنو التالي؟",
        ],
    },
    "relative_new_number": {
        "keyword": [
            "هاي رقمي الجديد بدل رقم، محتاج سلفة مستعجلة",
            "بدل رقم، ما اكدر اتصل، كلمني على الواتساب",
            "محتاج مبلغ مستعجل، رقمك القديم ما يشتغل، كلمني على الواتساب",
            "سلفة بسرعة، هذا رقمي الجديد، لا تثق بالرقم القديم",
            "هاتف صوري هو الوحيد اللي يشتغل، محتاج مبلغ",
            "الرقم القديم مطفي، سلفة على رقمي الجديد وكلمني عالواتساب",
        ],
        "silent": [
            "شنو الحل؟ محتاج مساعدة بسرية",
            "الجوال صوبح، ما أگدر أگولج",
            "رد عليج، وضع طارئ",
            "نرجع للحديث بعدين، الموضوع مهم",
            "شنو رأيك، نكمل بالطريقة اللي تحبج؟",
        ],
    },
    "advance_payment_seller": {
        "keyword": [
            "بيع تكي، ترسل دفعة مقدمة قبل الشحن ونحجز الطرد",
            "دفعة مقدمة قبل الشحن، بعدها الارسال بعد التحويل",
            "عربون نص المبلغ قبل الشحن، وخلاص الارسال بعد التحويل",
            "مبلغ مسبق وسلفة شراء عشان نحجز الطرد",
            "باقي المبلغ كدفعة مقدمة ونحجز الطرد قبل الشحن",
            "أريد الطرد اليوم، أرسل عربون وراح أرسل المبلغ قبل الشحن",
        ],
        "silent": [
            "المنتج موجود؟ كم آخر سعر؟",
            "أريد السلعة، كيف أدفع؟",
            "كم يوصلني إذا طلبت الحين؟",
            "المنتج مهملي، بعدين نكمل الكلام",
            "أريد أعرف التفاصيل أكثر، نچي",
        ],
    },
    "investment_doubling": {
        "keyword": [
            "استثمر معنا، أرباح مضمونة وعائد يومي",
            "منصة تداول جديدة، كل إطار نضاعف المبلغ، عائد يومي ثلاثة بالمئة",
            "استثمارك ينمو، صفقة مربحة كل أسبوع",
            "تداول معنا، استثمر مبلغك ونضاعفه",
            "أرباح مضمونة، مضاعفة فلوسك خلال شهر",
        ],
        "silent": [
            "شنو رأيك بالفرصة اللي شرحتها؟",
            "تحتاط التوقيع؟",
            "أريد أزيد دخلي، من وين أبدأ؟",
            "شلون تصير الأمور هسه؟",
            "تحب أرسلج التفاصيل؟",
        ],
    },
    "fake_refund": {
        "keyword": [
            "حسابك موقوف لتسوية مالية، أكد بياناتك وحوّل رسوم الاسترجاع",
            "المبلغ محجوز، البنك طالب التحقق، أرسل صورة البطاقة",
            "استرجاع المبلغ يحتاج تحديث بياناتك وتأكيد البيانات",
            "رسوم الاسترجاع يجب تأكيد البيانات",
            "تسوية مالية: المبلغ محجوز لحد ما تحدّث بياناتك",
        ],
        "silent": [
            "عندي مبلغ واصلني، شنو الخطوات؟",
            "حسابي موقوف بحكم، شنو أعمل؟",
            "المشكلة واصلة، كيف أحلها؟",
            "الموضوع واصلني، خلّيني أچيك",
            "شنو اللي يخصني أعمله بالضبط؟",
        ],
    },
}

# الحالات البريئة الصعبة (6.4)
BENIGN_KINDS = ["eid_family", "first_rent", "first_salary", "night_normal", "big_purchase"]


# ---------------------------------------------------------------- أدوات مساعدة
def make_ts(day: date, hour: int, minute: int, second: int = 0) -> str:
    return datetime.combine(day, time(hour, minute, second), tzinfo=BAGHDAD_TZ).isoformat()


def next_tx_id(user) -> str:
    user["n_tx"] += 1
    return f"t_{user['user_id']}_{user['n_tx']:05d}"


def bump_income(user, rng) -> int:
    """دخل (راتب/دفعة) يرفع الرصيد حتى ما تطلع تحويلات أكبر من الرصيد."""
    lo, hi = ARCHETYPES[user["archetype"]]["income"]
    amount = rng.randint(int(lo * 0.6), int(hi * 0.8))
    user["balance"] += amount
    return amount


def build_users(rng):
    """30 مستخدم: 20 dev + 10 test، وتوزيع متساوي على الأنماط الخمسة."""
    users = []
    for i in range(1, len(NAMES) + 1):
        user_id = f"u{i:02d}"
        arch_key = list(ARCHETYPES)[(i - 1) % len(ARCHETYPES)]
        arch = ARCHETYPES[arch_key]
        days = rng.randint(60, 120)
        contacts = []
        for j in range(1, rng.randint(*arch["contacts"]) + 1):
            # أغلب جهات الاتصال قديمة، وثلاث جهات حديثة
            age = rng.randint(1, 20) if j <= 3 else rng.randint(120, 900)
            contacts.append(
                {
                    "recipient_id": f"r_{user_id}_{j:02d}",
                    "age": age,
                    "weight": rng.uniform(0.5, 3.0),
                }
            )
        users.append(
            {
                "user_id": user_id,
                "name": NAMES[i - 1],
                "archetype": arch_key,
                "split": "dev" if i <= 20 else "test",
                "start_date": END_DATE - timedelta(days=days),
                "end_date": END_DATE,
                "contacts": contacts,
                "balance": rng.randint(*arch["start_balance"]),
                "typical": (arch["transfer"][0] + arch["transfer"][1]) // 2,
                "n_tx": 0,
            }
        )
    return users


def pick_contact(user, rng) -> dict:
    return rng.choices(user["contacts"], weights=[c["weight"] for c in user["contacts"]])[0]


def gen_normal_txs(user, rng) -> list:
    """معاملات طبيعية (6.3) + قليل من الساعات المتأخرة الواقعية (2%)."""
    arch = ARCHETYPES[user["archetype"]]
    rows = []
    day = user["start_date"]
    while day <= user["end_date"]:
        if day.day in arch["income_days"]:
            user["balance"] += rng.randint(*arch["income"])
        n_today = rng.choices([0, 1, 2, 3], weights=[8, 45, 35, 12])[0]
        if day == user["start_date"]:
            n_today = max(n_today, 1)  # نضمن بداية السجل من أول يوم (6.1)
        for _ in range(n_today):
            kind = rng.choices(
                ["transfer", "bill", "merchant", "new_recipient"], weights=[60, 20, 15, 5]
            )[0]
            if kind == "transfer":
                amount = rng.randint(*arch["transfer"])
                if user["archetype"] == "family_supporter" and rng.random() < 0.15:
                    amount = int(amount * rng.uniform(2.0, 3.2))  # مناسبة عائلية
                contact = pick_contact(user, rng)
                recipient_id, age = contact["recipient_id"], contact["age"]
                note, tx_type = rng.choice(TRANSFER_NOTES), "transfer"
            elif kind == "bill":
                amount = rng.randint(*arch["bill"])
                recipient_id = f"b_u_{user['user_id']}_{rng.randint(1, 4)}"
                age = rng.randint(200, 900)
                note, tx_type = rng.choice(BILL_NOTES), "bill"
            elif kind == "merchant":
                amount = rng.randint(*arch["merchant"])
                recipient_id = f"m_u_{user['user_id']}_{rng.randint(1, 6)}"
                age = rng.randint(30, 700)
                note, tx_type = rng.choice(MERCHANT_NOTES), "merchant"
            else:
                # 5% مستلم جديد بريء. "جديد" من ناحية المستخدم بس حسابه قديم:
                # جهة اتصال جديدة ما تعني حساب جديد، ومبلغ اعتيادي حتى ما يصير إنذار
                amount = int(user["typical"] * rng.uniform(0.15, 0.7))
                recipient_id = f"rn_{user['user_id']}_{rng.randint(1, 99)}"
                age = rng.randint(20, 400)
                note, tx_type = rng.choice(NEW_RECIPIENT_NOTES), "transfer"

            hour = rng.randint(0, 5) if rng.random() < 0.02 else rng.choice(arch["hours"])
            if amount > user["balance"] * 0.8:
                amount = max(5_000, int(user["balance"] * rng.uniform(0.2, 0.7)))
            rows.append(
                add_tx(
                    user, rng, day, hour, amount, tx_type, recipient_id, age,
                    note, None, 0, None, None,
                )
            )
            user["balance"] -= amount
            if user["balance"] < 300_000:
                bump_income(user, rng)
        day += timedelta(days=1)

    # 6.1: السجل لازم يغطي نافذة 60-120 يوم كاملة. نضمن معاملة واحدة بساعة متأخرة
    # بآخر يوم، وإلا ممكن آخر معاملة تقع قبل النافذة بيوم (المستخدم يطلع مداه 59 يوم)
    contact = pick_contact(user, rng)
    amount = rng.randint(*arch["transfer"])
    if amount > user["balance"] * 0.8:
        amount = max(5_000, int(user["balance"] * rng.uniform(0.2, 0.7)))
    rows.append(
        add_tx(user, rng, user["end_date"], 23, amount, "transfer",
               contact["recipient_id"], contact["age"], rng.choice(TRANSFER_NOTES),
               None, 0, None, None, minute=59)
    )
    return rows


def add_tx(user, rng, day, hour, amount, tx_type, recipient_id, age,
           note, context, is_scam, scam_type, case_id, minute=None, second=0) -> dict:
    """تضيف معاملة واحدة (الرصيدBefore محسوب قبل خصم المبلغ).

    minute اختياري: لو ما انمرّر نرمي دقيقة عشوائية، ولو انمرّر نحترمه بالضبط
    (الحالات السريعة والبطيئة تعتمد على توقيت دقيق).
    """
    amount = int(amount)
    if amount > user["balance"] * 0.8:
        bump_income(user, rng)
    row = {
        "tx_id": next_tx_id(user),
        "user_id": user["user_id"],
        "ts": make_ts(day, hour, rng.randint(0, 59) if minute is None else minute,
                      rng.randint(0, 59) if minute is None else second),
        "amount_iqd": amount,
        "balance_before_iqd": user["balance"],
        "tx_type": tx_type,
        "recipient_id": recipient_id,
        "recipient_age_days": age,
        "note": note,
        "context_message": context,
        "is_scam": is_scam,
        "scam_type": scam_type,
        "case_id": case_id,
    }
    user["balance"] -= amount
    return row


def day_pools(user, rng):
    """أيام متاحة لزرع الحالات: نتجنب أول 3 أيام وآخر 8 أيام (تحتاج للحالات البطيئة)."""
    span = (user["end_date"] - user["start_date"]).days
    days = [user["start_date"] + timedelta(days=d) for d in range(3, span - 7)]
    rng.shuffle(days)
    return days


def plant_benign_hard(user, kinds, rows, planted, pool, rng) -> None:
    """حالات بريئة صعبة (6.4)، كلها is_scam = 0."""
    arch = ARCHETYPES[user["archetype"]]
    for kind in kinds:
        day = rng.choice(pool)
        hour = rng.randint(9, 21)
        if kind == "eid_family":
            # تحويل عائلي كبير قبل العيد لقريب جديد بالقائمة بس حسابه قديم (FM1)
            rid, amount, age = f"rb_{user['user_id']}_{rng.randint(1, 5)}", rng.randint(600_000, 1_600_000), rng.randint(180, 400)
            note, tx_type, hour = "مبلغ العيد لأقربائي", "transfer", rng.randint(18, 22)
        elif kind == "first_rent":
            rid, amount, age = f"rr_{user['user_id']}_{rng.randint(1, 3)}", rng.randint(250_000, 600_000), rng.randint(30, 120)
            note, tx_type = "أول دفعة إيجار للمؤجر الجديد", "transfer"
        elif kind == "first_salary":
            rid, amount, age = f"rs_{user['user_id']}_{rng.randint(1, 3)}", rng.randint(600_000, 1_200_000), rng.randint(20, 90)
            note, tx_type = "أول راتب من جهة العمل الجديدة", "transfer"
        elif kind == "night_normal":
            # جهة معروفة => ما يفتح NEW_RECIPIENT، بس قد يفتح ODD_HOUR
            rid, amount, age = pick_contact(user, rng)["recipient_id"], rng.randint(*arch["transfer"]), 200
            note, tx_type, hour = None, "transfer", rng.randint(0, 4)
        else:  # big_purchase
            rid, amount, age = f"rm_{user['user_id']}_{rng.randint(1, 4)}", rng.randint(400_000, 2_500_000), rng.randint(30, 120)
            note, tx_type = rng.choice(["شراء جهاز", "شراء ذهب", "أثاث جديد"]), "merchant"
        bump_income(user, rng)
        row = add_tx(user, rng, day, hour, amount, tx_type, rid, age, note, None, 0, None, None)
        rows.append(row)
        planted.append(
            {
                "tx_id": row["tx_id"], "user_id": user["user_id"], "split": user["split"],
                "kind": kind, "scam_type": None, "case_id": None,
                "amount_iqd": row["amount_iqd"],
            }
        )


def plant_scam_case(user, scam_type, mode, case_no, rows, planted, pool, catalogue, variant_seen, rng) -> None:
    """حالة احتيال مزروعة (6.5): سريعة / بطيئة / صامتة، كلها لنفس الحالة case_id.

    - fast: 3 تحويلات خلال 10–20 دقيقة، مستلم جديد بحساب young، ونص فيه كلمات مفتاحية
    - slow: 6 تحويلات على 5–7 أيام تكبر تدريجياً، حساب قديم وبدون كلمات => يفوت أولها (FM2)
    - silent: تحويل واحد بمبلغ اعتيادي وحساب قديم وبدون كلمات => يفوت بالكامل (FM4)
    """
    arch = ARCHETYPES[user["archetype"]]
    is_silent = mode in ("slow", "silent")
    variants = SCAM_TEXTS[scam_type]["silent" if is_silent else "keyword"]
    # عدّاد لكل (نمط، نوع صياغة) مو عدّاد عام: لو كان عام تجابت حالتين من نفس
    # النمط على نفس الجملة، والشرط إنه كل حالة بصياغة مختلفة
    vkey = (scam_type, "silent" if is_silent else "keyword")
    seen = variant_seen.get(vkey, 0)
    message = variants[seen % len(variants)]
    variant_seen[vkey] = seen + 1

    case_id = f"c_{user['user_id']}_{scam_type}_{mode}_{case_no}"
    recipient_id = f"rs_{user['user_id']}_{scam_type}_{mode}"
    account_age = rng.randint(0, 6) if mode == "fast" else rng.randint(200, 800)
    start_day = rng.choice(pool)
    case_rows = []

    if mode == "fast":
        base = rng.randint(120_000, 400_000)
        hour, minute = rng.choice([21, 22, 23, 14, 15, 16, 19, 20]), rng.randint(0, 30)
        # 3 تحويلات تنحشر كلها ضمن 10-20 دقيقة (6.5)
        minutes = [0, rng.randint(4, 9), rng.randint(10, 20)]
        for k, amount in enumerate([base, int(base * 1.8), int(base * 2.5)]):
            bump_income(user, rng)
            case_rows.append(
                add_tx(user, rng, start_day, hour, int(amount), "transfer", recipient_id,
                       account_age, None, message, 1, scam_type, case_id, minute=minutes[k])
            )
    elif mode == "slow":
        # 6 تحويلات على 5-7 أيام، نفس الساعة حتى يكون الفارق بالأيام مضبوط (6.5)
        start_amount, span, hour = rng.randint(20_000, 45_000), rng.randint(5, 7), rng.randint(20, 23)
        for k in range(6):
            bump_income(user, rng)
            case_rows.append(
                add_tx(user, rng, start_day + timedelta(days=round(k * span / 5)), hour,
                       int(start_amount * 1.55 ** k), "transfer", recipient_id, account_age,
                       None, message, 1, scam_type, case_id, minute=0)
            )
    else:  # silent
        bump_income(user, rng)
        case_rows.append(
            add_tx(user, rng, start_day, rng.randint(10, 22), int(user["typical"] * rng.uniform(0.4, 0.9)),
                   "transfer", recipient_id, account_age, None, message, 1, scam_type, case_id)
        )

    # نتأكد من النصوص: الصامتة ما تطابق الكتالوج، والمكتشفة تطابق نمطها
    rows.extend(case_rows)
    matched = [m["id"] for m in match_catalogue(message, catalogue)]
    if is_silent and matched:
        raise AssertionError(f"نص صامت طلع يطابق {matched}: {message}")
    if not is_silent and scam_type not in matched:
        raise AssertionError(f"نص ما طابق نمطه {scam_type}: {message}")

    for row in case_rows:
        planted.append(
            {
                "tx_id": row["tx_id"], "user_id": user["user_id"], "split": user["split"],
                "kind": f"scam_{mode}", "scam_type": scam_type, "case_id": case_id,
                "amount_iqd": row["amount_iqd"],
            }
        )


def build_dataset(seed=SEED):
    """يرجع (users, transactions, planted) كاملاً بنفس البذرة."""
    random.seed(seed)  # البذرة الثابتة (قاعدة المشروع)
    rng = random.Random(seed)
    users = build_users(rng)
    catalogue = load_catalogue()
    modes = ["fast", "slow", "silent"]
    all_rows, planted = [], []
    scam_counter = {}
    variant_seen = {}

    for idx, user in enumerate(users):
        rows = gen_normal_txs(user, rng)
        pool = day_pools(user, rng)
        plant_benign_hard(user, [BENIGN_KINDS[idx % 5], BENIGN_KINDS[(idx + 3) % 5]],
                          rows, planted, pool, rng)
        for k, type_idx in enumerate([idx % 8, (idx + 4) % 8]):
            scam_type = list(SCAM_TEXTS)[type_idx % 8]
            n = scam_counter.get(scam_type, 0)
            scam_counter[scam_type] = n + 1
            plant_scam_case(user, scam_type, modes[n % 3], k, rows, planted, pool,
                            catalogue, variant_seen, rng)
        rows.sort(key=lambda r: r["ts"])
        all_rows.extend(rows)
    return users, all_rows, planted


def write_csv(path, columns, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarise(users, txs, planted) -> list:
    """ملخص الأرقام المطلوب طباعته."""
    dev_ids = {u["user_id"] for u in users if u["split"] == "dev"}
    test_ids = {u["user_id"] for u in users if u["split"] == "test"}
    dev_txs = [t for t in txs if t["user_id"] in dev_ids]
    test_txs = [t for t in txs if t["user_id"] in test_ids]
    lines = ["=== ملخص البيانات الاصطناعية ==="]
    lines.append(f"مستخدمون: {len(users)} (dev={len(dev_ids)} / test={len(test_ids)})")
    for key, arch in ARCHETYPES.items():
        lines.append(f"  {arch['label_ar']:<14}: {len([u for u in users if u['archetype'] == key])} مستخدم")
    lines.append(f"معاملات: {len(txs)} (dev={len(dev_txs)} / test={len(test_txs)})")
    lines.append(f"معدل المعاملات لكل مستخدم: {len(txs) / len(users):.0f}")
    kinds = {}
    for t in txs:
        kinds[t["tx_type"]] = kinds.get(t["tx_type"], 0) + 1
    lines.append("توزيع الأنواع: " + " ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    amounts = sorted(t["amount_iqd"] for t in txs)
    lines.append(f"المبالغ: أصغر={amounts[0]:,} وسط={amounts[len(amounts) // 2]:,} أكبر={amounts[-1]:,}")

    cases = {}
    for p in planted:
        if p["kind"].startswith("scam"):
            cases.setdefault(p["case_id"], p)
    for split in ("dev", "test"):
        subset = [c for c in cases.values() if c["split"] == split]
        per_type = {}
        for c in subset:
            per_type[c["scam_type"]] = per_type.get(c["scam_type"], 0) + 1
        lines.append(f"حالات احتيال {split}: {len(subset)}")
        lines.append("  " + " ".join(f"{k}={v}" for k, v in sorted(per_type.items())))
    for mode in ("fast", "slow", "silent"):
        lines.append(f"  {mode}: {len([c for c in cases.values() if c['kind'] == f'scam_{mode}'])}")

    benign = [p for p in planted if not p["kind"].startswith("scam")]
    for split in ("dev", "test"):
        n = len([b for b in benign if b["split"] == split])
        lines.append(f"حالات بريئة صعبة {split}: {n}")
    lines.append("  " + " ".join(
        f"{k}={len([b for b in benign if b['kind'] == k])}" for k in BENIGN_KINDS
    ))
    return lines


def check_requirements(users, txs, planted) -> None:
    """شروط لازم تتحقق قبل كتابة الملفات (6.1 و6.4)."""
    cases = {}
    for p in planted:
        if p["kind"].startswith("scam"):
            cases.setdefault(p["case_id"], p)
    dev_cases = [c for c in cases.values() if c["split"] == "dev"]
    test_cases = [c for c in cases.values() if c["split"] == "test"]
    assert len(users) == 30, f"لازم 30 مستخدم، موجود {len(users)}"
    assert len(dev_cases) >= 30, f"dev لازم >=30 حالة، موجود {len(dev_cases)}"
    assert len(test_cases) >= 15, f"test لازم >=15 حالة، موجود {len(test_cases)}"
    for scam_type in SCAM_TEXTS:
        n = len([c for c in test_cases if c["scam_type"] == scam_type])
        assert n >= 2, f"النمط {scam_type} لازم >=2 حالة باختبار، موجود {n}"
    benign_test = [p for p in planted if not p["kind"].startswith("scam") and p["split"] == "test"]
    assert len(benign_test) >= 10, f"test لازم >=10 حالة صعبة، موجود {len(benign_test)}"
    assert len({t["tx_id"] for t in txs}) == len(txs), "معرفات معاملة مكررة"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    users, txs, planted = build_dataset()
    check_requirements(users, txs, planted)

    user_rows = [{k: u[k] for k in USER_COLUMNS} for u in users]
    dev_ids = {u["user_id"] for u in users if u["split"] == "dev"}
    # عينة المراجعة اليدوية (6.6): 50 معاملة عشوائية + كل الحالات المزروعة
    rng = random.Random(SEED)
    sample_ids = {t["tx_id"] for t in rng.sample(txs, 50)}
    sample_ids |= {p["tx_id"] for p in planted}
    sample = [t for t in txs if t["tx_id"] in sample_ids]

    outputs = {
        SYNTH_DIR / "users.csv": (USER_COLUMNS, user_rows),
        SYNTH_DIR / "transactions.csv": (TX_COLUMNS, [t for t in txs if t["user_id"] in dev_ids]),
        SYNTH_DIR / "review_sample.csv": (TX_COLUMNS, sample),
        SEALED_DIR / "users.csv": (USER_COLUMNS, user_rows),
        SEALED_DIR / "transactions.csv": (TX_COLUMNS, [t for t in txs if t["user_id"] not in dev_ids]),
    }
    for path, (columns, rows) in outputs.items():
        write_csv(path, columns, rows)

    print("\n".join(summarise(users, txs, planted)))
    print(f"عينة المراجعة اليدوية: {len(sample)} معاملة")
    print("الملفات:")
    for path in outputs:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
