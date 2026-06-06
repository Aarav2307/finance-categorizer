"""Unit tests for recurring.py — run with: python -m pytest test_recurring.py -v"""

import pytest
from datetime import date
from recurring import normalize_merchant, detect_recurring, _split_amount_tiers


# ── normalize_merchant ────────────────────────────────────────────────────────

def test_aplpay_prefix_stripped():
    result = normalize_merchant("AplPay APPLE.COM/BILL")
    assert "APLPAY" not in result

def test_apple_slash_variants_same_key():
    # Both AMEX forms of the Apple subscription must collapse to the same key
    k1 = normalize_merchant("AplPay APPLE.COM/BILL")
    k2 = normalize_merchant("AplPay APPLE.COM/BILINTERNET CHARGE")
    assert k1 == k2, f"Expected same key, got {k1!r} and {k2!r}"
    assert k1 == "APPLE.COM"

def test_openai_chatgpt_with_trailing_id():
    # Asterisk replaced by space; 6-digit ID stripped
    assert normalize_merchant("OPENAI *CHATGPT 882736") == "OPENAI CHATGPT"

def test_openai_chatgpt_no_id():
    # Asterisk replaced by space; no ID to strip
    assert normalize_merchant("OPENAI *CHATGPT") == "OPENAI CHATGPT"

def test_sq_blue_bottle():
    # SQ * is a Square payment-processor prefix — strip it
    assert normalize_merchant("SQ *BLUE BOTTLE COFF") == "BLUE BOTTLE COFF"

def test_tst_prefix_stripped():
    assert normalize_merchant("TST* CHIPOTLE") == "CHIPOTLE"

def test_paypal_prefix_stripped():
    assert normalize_merchant("PAYPAL *VENMO") == "VENMO"

def test_pp_asterisk_stripped():
    assert normalize_merchant("PP*GAME PURCHASE") == "GAME PURCHASE"

def test_store_number_stripped():
    assert normalize_merchant("STARBUCKS #1234") == "STARBUCKS"

def test_trailing_long_id_stripped():
    assert normalize_merchant("LYFT 8834720") == "LYFT"

def test_corp_suffix_stripped():
    assert normalize_merchant("NETFLIX INC") == "NETFLIX"

def test_plain_merchant_unchanged():
    assert normalize_merchant("SPOTIFY") == "SPOTIFY"

def test_aplpay_normalises_to_same_as_plain():
    # An AplPay prefix on the same merchant shouldn't create a different group
    assert normalize_merchant("AplPay SPOTIFY") == normalize_merchant("SPOTIFY")


# ── detect_recurring — interval detection ────────────────────────────────────

def _t(desc, amount, date_str):
    return {"description": desc, "amount": amount, "date": date_str}

def test_monthly_detection_clean():
    txns = [
        _t("NETFLIX", -15.99, "01/01/2025"),
        _t("NETFLIX", -15.99, "02/01/2025"),
        _t("NETFLIX", -15.99, "03/01/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 1))
    assert any(p["frequency"] == "monthly" and p["merchant_key"] == "NETFLIX" for p in patterns)

def test_monthly_detection_variable_billing_days():
    # Subscription processed on the 1st, 3rd, and 1st across three months
    # Intervals: 33, 29 — average 31, clearly monthly
    txns = [
        _t("SPOTIFY", -9.99, "01/01/2025"),
        _t("SPOTIFY", -9.99, "02/03/2025"),  # 33 days later
        _t("SPOTIFY", -9.99, "03/04/2025"),  # 29 days later
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 4))
    monthly = [p for p in patterns if p["frequency"] == "monthly" and "SPOTIFY" in p["merchant_key"]]
    assert monthly, "SPOTIFY with 31-day average should be classified as monthly"

def test_monthly_at_lower_boundary():
    # 21-day intervals — should now pass with the widened 20–40 window
    txns = [
        _t("HULU", -7.99, "01/01/2025"),
        _t("HULU", -7.99, "01/22/2025"),  # 21 days
        _t("HULU", -7.99, "02/12/2025"),  # 21 days
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 2, 12))
    assert any(p["frequency"] == "monthly" for p in patterns)

def test_weekly_detection():
    txns = [
        _t("GYM PARKING", -5.00, "01/01/2025"),
        _t("GYM PARKING", -5.00, "01/08/2025"),  # 7 days
        _t("GYM PARKING", -5.00, "01/15/2025"),  # 7 days
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 1, 15))
    assert any(p["frequency"] == "weekly" for p in patterns)

def test_annual_detection():
    txns = [
        _t("AMAZON PRIME", -139.00, "03/15/2024"),
        _t("AMAZON PRIME", -139.00, "03/20/2025"),  # 370 days — within 350–380
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 20))
    assert any(p["frequency"] == "annual" for p in patterns)

def test_amazon_marketplace_blocked():
    # Regular Amazon purchases should never appear as recurring
    txns = [_t("AMZN MKTP US", -23.50, f"0{i}/15/2025") for i in range(1, 4)]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 15))
    assert not any("AMZN" in p["merchant_key"] or "AMAZON" in p["merchant_key"] for p in patterns)

def test_raising_canes_blocked():
    txns = [_t("RAISING CANES", -12.50, f"0{i}/10/2025") for i in range(1, 4)]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 10))
    assert not any("RAISING CANE" in p["merchant_key"] for p in patterns)


# ── detect_recurring — frequent tier ─────────────────────────────────────────

def test_frequent_detection():
    # Near-daily occurrences: avg ~2 days — not in any interval window → frequent
    txns = [
        _t("CANTEEN VENDING", -2.50, "01/01/2025"),
        _t("CANTEEN VENDING", -1.75, "01/02/2025"),  # 1 day
        _t("CANTEEN VENDING", -2.50, "01/04/2025"),  # 2 days
        _t("CANTEEN VENDING", -3.00, "01/05/2025"),  # 1 day
        _t("CANTEEN VENDING", -2.75, "01/07/2025"),  # 2 days
    ]
    # avg interval = 1.5 days — outside weekly (5–9), monthly (20–40), annual
    patterns = detect_recurring(txns, reference_date=date(2025, 1, 31))
    freq = [p for p in patterns if p["frequency"] == "frequent"]
    assert len(freq) == 1
    assert "CANTEEN VENDING" in freq[0]["merchant_key"]

def test_frequent_requires_5_occurrences():
    # Only 4 occurrences — should NOT appear as frequent
    txns = [
        _t("VENDING A", -1.50, "01/01/2025"),
        _t("VENDING A", -1.50, "01/02/2025"),
        _t("VENDING A", -1.50, "01/03/2025"),
        _t("VENDING A", -1.50, "01/04/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 1, 31))
    assert not any(p["frequency"] == "frequent" for p in patterns)

def test_frequent_excluded_from_fixed_monthly():
    # A frequent merchant should not have frequency=='monthly'
    txns = [
        _t("COFFEE CART", -3.00, "01/01/2025"),
        _t("COFFEE CART", -3.00, "01/02/2025"),
        _t("COFFEE CART", -3.00, "01/03/2025"),
        _t("COFFEE CART", -3.00, "01/04/2025"),
        _t("COFFEE CART", -3.00, "01/05/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 1, 31))
    # None of the frequent patterns should have frequency=='monthly'
    assert not any(
        p["merchant_key"] == "COFFEE CART" and p["frequency"] == "monthly"
        for p in patterns
    )


# ── _split_amount_tiers ───────────────────────────────────────────────────────

def _e(amount):
    """Minimal entry dict for tier-splitting tests."""
    return {"description": "X", "amount": amount, "date": None}

def test_single_tier_all_same():
    entries = [_e(-9.99)] * 4
    tiers = _split_amount_tiers(entries)
    assert len(tiers) == 1
    assert len(tiers[0]) == 4

def test_single_tier_similar_amounts():
    # 9.99, 10.49, 10.99 — all within 25% of each other → one tier
    entries = [_e(-9.99), _e(-10.49), _e(-10.99)]
    tiers = _split_amount_tiers(entries)
    assert len(tiers) == 1

def test_two_tiers_distinct():
    # 2.99 × 4 and 39.70 × 1 — differ by >25% → two tiers
    entries = [_e(-2.99)] * 4 + [_e(-39.70)]
    tiers = _split_amount_tiers(entries)
    assert len(tiers) == 2
    amounts_by_tier = [sorted(abs(e["amount"]) for e in t) for t in tiers]
    assert amounts_by_tier[0] == [2.99, 2.99, 2.99, 2.99]
    assert amounts_by_tier[1] == [39.70]

def test_three_tiers():
    entries = [_e(-2.99)] * 2 + [_e(-9.99)] * 2 + [_e(-99.99)] * 2
    tiers = _split_amount_tiers(entries)
    assert len(tiers) == 3

def test_empty_entries():
    assert _split_amount_tiers([]) == []

def test_single_entry():
    entries = [_e(-5.00)]
    tiers = _split_amount_tiers(entries)
    assert len(tiers) == 1
    assert len(tiers[0]) == 1


# ── detect_recurring — amount-tier splitting integrated ──────────────────────

def test_tier_split_only_one_qualifies_no_label():
    # $2.99 × 4 (monthly) + $39.70 × 1 (insufficient occurrences)
    # Only the $2.99 tier qualifies → no amount label appended to display_name
    txns = [
        _t("APPLE.COM", -2.99, "10/10/2025"),
        _t("APPLE.COM", -2.99, "11/10/2025"),
        _t("APPLE.COM", -2.99, "12/10/2025"),
        _t("APPLE.COM", -2.99, "01/10/2026"),
        _t("APPLE.COM", -39.70, "09/29/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2026, 1, 10))
    assert len(patterns) == 1
    assert abs(patterns[0]["typical_amount"]) == pytest.approx(2.99)
    assert patterns[0]["frequency"] == "monthly"
    assert "(" not in patterns[0]["display_name"], "no amount label when only one tier qualifies"

def test_tier_split_both_qualify_get_labels():
    # $9.99 × 3 monthly + $29.99 × 3 monthly → 2 patterns, each with amount label
    txns = [
        _t("SERVICE", -9.99, "01/01/2025"),
        _t("SERVICE", -9.99, "02/01/2025"),
        _t("SERVICE", -9.99, "03/01/2025"),
        _t("SERVICE", -29.99, "01/15/2025"),
        _t("SERVICE", -29.99, "02/15/2025"),
        _t("SERVICE", -29.99, "03/15/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 15))
    assert len(patterns) == 2
    names = {p["display_name"] for p in patterns}
    assert any("9.99" in n for n in names)
    assert any("29.99" in n for n in names)
    # Both should still be identified as monthly
    assert all(p["frequency"] == "monthly" for p in patterns)

def test_tier_split_merchant_key_unchanged():
    # merchant_key must remain the same for both tiers (cache lookup uses it)
    txns = [
        _t("SERVICE", -9.99, "01/01/2025"),
        _t("SERVICE", -9.99, "02/01/2025"),
        _t("SERVICE", -9.99, "03/01/2025"),
        _t("SERVICE", -29.99, "01/15/2025"),
        _t("SERVICE", -29.99, "02/15/2025"),
        _t("SERVICE", -29.99, "03/15/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 15))
    assert all(p["merchant_key"] == "SERVICE" for p in patterns)

def test_tier_split_occurrence_counts_independent():
    # Each tier's occurrence count should reflect only its own transactions
    txns = [
        _t("SVC", -9.99, "01/01/2025"),
        _t("SVC", -9.99, "02/01/2025"),
        _t("SVC", -9.99, "03/01/2025"),
        _t("SVC", -29.99, "01/15/2025"),
        _t("SVC", -29.99, "02/15/2025"),
        _t("SVC", -29.99, "03/15/2025"),
    ]
    patterns = detect_recurring(txns, reference_date=date(2025, 3, 15))
    assert len(patterns) == 2
    assert all(p["occurrences"] == 3 for p in patterns)
