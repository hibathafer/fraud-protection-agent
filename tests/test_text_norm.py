"""اختبارات تطبيع النص العربي (قسم 5)."""

from src.detection.rules import combined_text, normalize_text


def test_removes_diacritics():
    assert normalize_text("مُحَمَّد") == "محمد"
    assert normalize_text("مُرْحَباً") == "مرحبا"
    assert normalize_text("جَائِزَة") == "جايزه"


def test_removes_tatweel():
    assert normalize_text("مـــحمد") == "محمد"
    assert normalize_text("مصــطفى") == "مصطفي"


def test_unifies_alef_forms():
    assert normalize_text("أحمد") == "احمد"
    assert normalize_text("إسلام") == "اسلام"
    assert normalize_text("آمن") == "امن"
    # الألف اليسرية (ٱ) تصير ألف عادية
    assert normalize_text("ٱمان") == "امان"


def test_unifies_yaa_and_taa_marbuta():
    assert normalize_text("مصطفى") == "مصطفي"
    assert normalize_text("جائزة") == "جايزه"
    assert normalize_text("رسوم") == "رسوم"
    assert normalize_text(" Data ") == "data"


def test_unifies_waw_and_yea_hamza():
    assert normalize_text("مسؤول") == "مسوول"
    assert normalize_text("تأكيد") == "تاكيد"
    # اللي يكتب بدون همزة يطلع نفس النص
    assert normalize_text("تاكيد") == normalize_text("تأكيد")
    assert normalize_text("مسوول") == normalize_text("مسؤول")


def test_punctuation_becomes_space_and_collapses():
    assert normalize_text("مُرْحَباً، بكَرة!") == "مرحبا بكره"
    # لاحظ: "سلفة" تصير "سلفه" (تاء مربوطة)، و"للبيت" ما تصير "للبت"
    assert normalize_text("سلفة\n\nللبيت  .. حتى يوم Friday") == "سلفه للبيت حتي يوم friday"


def test_lowercases_english():
    assert normalize_text("OTP Request") == "otp request"
    assert normalize_text("Otp") == "otp"


def test_keeps_digits():
    assert normalize_text("100000 دينار") == "100000 دينار"
    assert normalize_text("GBP 5,000") == "gbp 5 000"


def test_empty_inputs():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_is_idempotent():
    for raw in ["مُحَمَّد", "أحمد إسلام", "مسؤول", "OTP Request", "جائزة"]:
        once = normalize_text(raw)
        assert normalize_text(once) == once


def test_same_meaning_different_spelling():
    # "إستعجل" و"استعجل" لازم يطلعون نفس النص
    assert normalize_text("إستعجل") == normalize_text("استعجل")
    # "مُرْسَل" و"مرسل"
    assert normalize_text("مُرْسَل") == normalize_text("مرسل")


def test_combined_text_joins_note_and_message():
    assert combined_text("رسوم", "حوّل الجائزة") == "رسوم حول الجايزه"
    assert combined_text(None, "رمز التحقق") == "رمز التحقق"
    assert combined_text("الفاتورة", None) == "الفاتوره"
    assert combined_text(None, None) == ""
