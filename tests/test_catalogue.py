"""اختبارات كتالوج الأنماط ومطابقته (قسم 5)."""

from src.detection.rules import load_catalogue, match_catalogue

# أمثلة بصياغات مختلفة لكل نمط (سيناريوهات مزروعة بقسم 6.5)
SAMPLES = {
    "otp_fake_agent": "موظف الدعم يطلب رمز تحقق منك، بعده يفعّل الحساب",
    "prize_fee": "مبروك ربحت الجائزة، حول رسوم المعالجة ونرسل لك المكافأة",
    "safe_account": "حسابك مخترق، حوّل المبلغ لحساب أمان، بعدها نرجّعه",
    "fake_job_fee": "وظيفة جديدة، تدفع رسوم التسجيل وبعدها التقديم ينجح",
    "relative_new_number": "هاي رقمي الجديد بدل رقم، محتاج سلفة مستعجلة",
    "advance_payment_seller": "بيع تكي، ترسل دفعة مقدمة قبل الشحن ونحجز الطرد",
    "investment_doubling": "استثمر معنا، أرباح مضمونة وعائد يومي",
    "fake_refund": "حسابك موقوف لتسوية مالية، أكد بياناتك وحوّل رسوم الاسترجاع",
}

BENIGN = [
    "تحويل راتب شهري لمحمود",
    "دفع فاتورة الكهرباء",
    "سلفة البيت لشهر رمضان",  # كلمة "سلفة" وحدة ما تكفي (الحد 2)
    "شراء موبايل من محل، دفعت بالموقع",
    "هاي أول مرة نحچي بيه، حول مبلغ وبعدها نكمل",  # احتيال صامت بدون كلمات مفتاحية
]

EXPECTED_IDS = set(SAMPLES)


def test_catalogue_is_list_of_eight_patterns():
    catalogue = load_catalogue()
    assert isinstance(catalogue, list)
    assert len(catalogue) == 8
    assert {p["id"] for p in catalogue} == EXPECTED_IDS


def test_pattern_shape_is_valid():
    required = {"id", "name_ar", "keywords_ar", "min_keyword_hits",
                "typical_next_line_ar", "advice_ar", "weight"}
    for pattern in load_catalogue():
        assert required <= set(pattern), pattern["id"]
        assert len(pattern["keywords_ar"]) >= 5, pattern["id"]
        assert len(set(pattern["keywords_ar"])) == len(pattern["keywords_ar"]), pattern["id"]
        assert all(isinstance(k, str) and k.strip() for k in pattern["keywords_ar"])
        assert 1 <= pattern["min_keyword_hits"] <= len(pattern["keywords_ar"])
        assert isinstance(pattern["weight"], int) and pattern["weight"] > 0
        for field in ("id", "name_ar", "typical_next_line_ar", "advice_ar"):
            assert pattern[field].strip(), (pattern["id"], field)


def test_every_pattern_matches_its_sample():
    catalogue = load_catalogue()
    for pattern_id, sample in SAMPLES.items():
        matches = match_catalogue(sample, catalogue)
        assert pattern_id in [m["id"] for m in matches], (pattern_id, sample)


def test_match_returns_hits_and_coaching_fields():
    catalogue = load_catalogue()
    best = match_catalogue(SAMPLES["prize_fee"], catalogue)[0]
    assert best["id"] == "prize_fee"
    assert len(best["keyword_hits"]) >= 2
    assert best["weight"] == 35
    assert best["typical_next_line_ar"]
    assert best["advice_ar"]


def test_benign_text_does_not_match():
    catalogue = load_catalogue()
    for text in BENIGN:
        assert match_catalogue(text, catalogue) == [], text


def test_single_keyword_is_not_enough():
    # min_keyword_hits = 2 لكل الأنماط، فكلمة وحدة ما تكفي
    catalogue = load_catalogue()
    for pattern in catalogue:
        one = pattern["keywords_ar"][0]
        assert match_catalogue(one, catalogue) == [], one


def test_matching_ignores_orthography_and_diacritics():
    catalogue = load_catalogue()
    # نفس الرسالة برسوم مختلفة (تشكيل + همزات) ترجّع نفس النمط
    assert [m["id"] for m in match_catalogue(SAMPLES["prize_fee"], catalogue)] == [
        m["id"] for m in match_catalogue("مُبْرُوك رَبَحْت الجَائِزَة، حَوِّل رُسُوم المُعَالَجَة", catalogue)
    ]


def test_empty_text_returns_no_matches():
    catalogue = load_catalogue()
    assert match_catalogue("", catalogue) == []
    assert match_catalogue(None, catalogue) == []
