"""تطبيع النص العربي ومطابقة كتالوج أنماط الاحتيال (قسم 5) + قواعد الكشف (7.2).

كل قاعدة دالة ترجع Reason (نقاط + سبب بالعربي) أو None.
"""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from src.config import (
    AMOUNT_HIGH_FALLBACK,
    AMOUNT_HIGH_FACTOR,
    CATALOGUE_PATH,
    CUMULATIVE_DAYS,
    CUMULATIVE_MIN_COUNT,
    CUMULATIVE_SUM_FACTOR,
    DRAIN_RATIO,
    MIN_TX_FOR_PROFILE,
    ODD_HOURS,
    POINTS,
    RAPID_MIN_COUNT,
    TRUSTED_MIN_COUNT,
    TRUSTED_MIN_SPAN_DAYS,
    YOUNG_ACCOUNT_DAYS,
)
from src.detection.features import parse_ts


# التشكيل (فتحات..سكون، علامات قرآنية) + التطويل ـ
_MARKS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
# كل شي مو حرف/رقم يصير فراغ (فاصلة، نقطة، سطر جديد...)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_SPACES = re.compile(r"\s+")

# توحيد رسم الحروف: الهمزات، الألف المقصورة، التاء المربوطة، الهمزة
_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ئ": "ي",
        "ؤ": "و",
        "ة": "ه",
        "ۀ": "ه",
        "ء": "",
    }
)


def normalize_text(text):
    """يوحّد النص قبل المقارنة: يشيل التشكيل، يوحّد الحروف، ويصغّر الإنجليزي."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = _MARKS.sub("", s)
    s = s.translate(_LETTERS)
    s = s.lower()
    s = _NON_WORD.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


def combined_text(note=None, context_message=None):
    """النص المستعمل للمطابقة = note + context_message (قسم 5)."""
    parts = [p for p in (note, context_message) if p]
    return normalize_text(" ".join(str(p) for p in parts))


def load_catalogue(path=None):
    """يقرأ data/scam_catalogue.json ويرجع قائمة الأنماط."""
    catalogue_path = Path(path) if path else CATALOGUE_PATH
    with open(catalogue_path, encoding="utf-8") as f:
        catalogue = json.load(f)
    if not isinstance(catalogue, list):
        raise ValueError("كتالوج الأنماط لازم يكون قائمة JSON")
    return catalogue


def match_catalogue(text, catalogue=None):
    """يرجع الأنماط المطابقة للنص، مرتبة من الأكثر كلمات للأقل."""
    if catalogue is None:
        catalogue = load_catalogue()
    haystack = normalize_text(text)
    if not haystack:
        return []

    matches = []
    for pattern in catalogue:
        hits = [kw for kw in pattern["keywords_ar"] if normalize_text(kw) in haystack]
        if len(hits) >= pattern.get("min_keyword_hits", 1):
            matches.append(
                {
                    "id": pattern["id"],
                    "name_ar": pattern["name_ar"],
                    "weight": pattern["weight"],
                    "keyword_hits": hits,
                    "typical_next_line_ar": pattern.get("typical_next_line_ar", ""),
                    "advice_ar": pattern.get("advice_ar", ""),
                }
            )
    matches.sort(key=lambda m: (-len(m["keyword_hits"]), -m["weight"]))
    return matches


# ----------------------------------------------------------------- قواعد الكشف (7.2)
@dataclass
class Reason:
    """سبب مكتوب بالعربي، حتى يكون كل قرار قابل للتفسير والمراجعة."""

    rule_id: str
    points: int
    text_ar: str

    def to_dict(self) -> dict:
        return asdict(self)


def _is_transfer(tx) -> bool:
    """قواعد المستلم تنطبق على التحويلات فقط (7.2: أول تحويل)."""
    return tx.get("tx_type", "transfer") == "transfer"


def rule_new_recipient(tx, profile):
    if not _is_transfer(tx):
        return None
    if profile["recipient"]["count"] == 0:
        return Reason("NEW_RECIPIENT", POINTS["NEW_RECIPIENT"], "أول مرة تحوّل لهذا الشخص")
    return None


def rule_young_recipient_account(tx, profile):
    if not _is_transfer(tx):
        return None
    age = tx.get("recipient_age_days")
    if profile["recipient"]["count"] == 0 and age is not None and age < YOUNG_ACCOUNT_DAYS:
        return Reason(
            "YOUNG_RECIPIENT_ACCOUNT",
            POINTS["YOUNG_RECIPIENT_ACCOUNT"],
            f"حساب المستلم فتح من {age} يوم فقط",
        )
    return None


def rule_amount_high(tx, profile):
    limit = max(AMOUNT_HIGH_FACTOR * profile["median_amount"], profile["p95_amount"])
    if profile["n_tx"] < MIN_TX_FOR_PROFILE:
        limit = AMOUNT_HIGH_FALLBACK  # تاريخ قصير: عتبة ثابتة بدل إحصاء موثوق
    amount = int(tx["amount_iqd"])
    if amount > limit:
        return Reason(
            "AMOUNT_HIGH",
            POINTS["AMOUNT_HIGH"],
            f"المبلغ {amount:,} أكبر بكثير من عادتك (الحد {int(limit):,})",
        )
    return None


def rule_balance_drain(tx, profile):
    balance = int(tx.get("balance_before_iqd") or 0)
    if balance > 0 and int(tx["amount_iqd"]) >= DRAIN_RATIO * balance:
        return Reason(
            "BALANCE_DRAIN",
            POINTS["BALANCE_DRAIN"],
            f"المبلغ ياخذ {int(tx['amount_iqd'] / balance * 100)}% من رصيدك",
        )
    return None


def rule_odd_hour(tx, profile):
    hour = parse_ts(tx["ts"]).hour
    if hour in ODD_HOURS and hour not in profile["typical_hours"]:
        return Reason("ODD_HOUR", POINTS["ODD_HOUR"], f"ساعة غريبة: {hour}:00 بعد منتصف الليل")
    return None


def rule_rapid_sequence(tx, profile):
    # العدد يشمل المعاملة الحالية
    if profile["recent_tx_30min"] + 1 >= RAPID_MIN_COUNT:
        return Reason(
            "RAPID_SEQUENCE",
            POINTS["RAPID_SEQUENCE"],
            f"{profile['recent_tx_30min'] + 1} تحويلات خلال 30 دقيقة",
        )
    return None


def rule_scam_pattern(tx, profile, catalogue=None):
    """ترجع (Reason, تفاصيل النمط) إذا طابق النص، وتترك None إذا ما طابق."""
    text = combined_text(tx.get("note"), tx.get("context_message"))
    matches = match_catalogue(text, catalogue)
    if not matches:
        return None
    best = matches[0]
    return Reason(
        "SCAM_PATTERN",
        best["weight"],
        f"الرسالة تطابق نمط معروف: {best['name_ar']}",
    ), best


def rule_cumulative_new_recipient(tx, profile):
    """للاحتيال البطيء: 3 تحويلات لنفس المستلم الجديد بآخر 7 أيام (7.2)."""
    first_ts = profile["recipient"]["first_ts"]
    if first_ts is None:
        return None  # ما نعرفه بعد = ما انفتح بعد
    age_days = (parse_ts(tx["ts"]) - first_ts).total_seconds() / 86400
    count = profile["sent_to_recipient_7d"]["count"] + 1  # تشم المعاملة الحالية
    total = profile["sent_to_recipient_7d"]["sum_iqd"] + int(tx["amount_iqd"])
    if (
        age_days <= CUMULATIVE_DAYS
        and count >= CUMULATIVE_MIN_COUNT
        and total >= CUMULATIVE_SUM_FACTOR * profile["median_amount"]
    ):
        return Reason(
            "CUMULATIVE_NEW_RECIPIENT",
            POINTS["CUMULATIVE_NEW_RECIPIENT"],
            f"تحويلات صغيرة متراكمة لنفس المستلم الجديد: {count} تحويلات ومجموعها {total:,}",
        )
    return None


def rule_trusted_recipient(tx, profile):
    info = profile["recipient"]
    trusted = (
        info["count"] >= TRUSTED_MIN_COUNT and info["span_days"] >= TRUSTED_MIN_SPAN_DAYS
    ) or profile["trusted"]
    if trusted:
        return Reason(
            "TRUSTED_RECIPIENT",
            POINTS["TRUSTED_RECIPIENT"],
            "هالمستلم موثوق وعندك تاريخ طويل وياه",
        )
    return None


# القواعد اللي ما تعتمد على كتالوج الأنماط
# ملاحظة: TRUSTED_RECIPIENT و SCAM_PATTERN مو هنا، المحرك يناديهم لأن ترتيبهما
# يعتمد على نتيجة بعض (7.2).
RULES = [
    rule_new_recipient,
    rule_young_recipient_account,
    rule_amount_high,
    rule_balance_drain,
    rule_odd_hour,
    rule_rapid_sequence,
    rule_cumulative_new_recipient,
]

