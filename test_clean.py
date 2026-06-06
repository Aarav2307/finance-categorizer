"""Unit tests for clean.py — run with: python -m pytest test_clean.py -v"""

import pytest
from clean import clean_description


# ── Spec examples (all 15 required cases) ────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    # Dictionary hits
    ("AplPay CTLP*CANTEEN CHARLOTTE",             "Canteen Vending"),
    ("AplPay CPI*CANTEEN VFITCHBURG",             "Canteen Vending"),
    ("UBER EATS help.uber.com",                   "Uber Eats"),
    ("AplPay 7-ELEVEN 3372CHICAGO",               "7-Eleven"),
    ("OPENAI *CHATGPT SUBSSAN FRANCISCO",         "ChatGPT"),
    ("AplPay APPLE.COM/BILINTERNET CHARGE",       "Apple"),
    ("AMAZON.COM AMZN.COM/BILL",                  "Amazon"),
    ("THE NORTH FACE.COM (888)863-1968",          "The North Face"),
    ("AplPay RAISING CANESMADISON",               "Raising Cane's"),
    ("AplPay PINKUS MARKETMADISON",               "Pinkus Market"),
    ("PAR*MOKA - BOOKSTOREMADISON",               "Moka"),
    ("AplPay STOP N SHOP #MADISON",               "Stop N Shop"),
    ("AplPay TACO BELL 300MADISON",               "Taco Bell"),
    ("AplPay TARGET",                             "Target"),
    # Generic stripping
    ("SP ALDO",                                   "Aldo"),
])
def test_spec_examples(raw, expected):
    assert clean_description(raw) == expected, f"Input: {raw!r}"


# ── Dictionary — key selection ────────────────────────────────────────────────

def test_longest_key_wins_amazon_vs_amzn():
    # Both AMAZON and AMZN match; AMAZON is longer and should win (same result)
    assert clean_description("AMAZON.COM AMZN.COM/BILL") == "Amazon"

def test_dictionary_case_insensitive():
    assert clean_description("Netflix") == "Netflix"
    assert clean_description("NETFLIX") == "Netflix"

def test_apple_bill_variant():
    assert clean_description("APPLE.COM/BILL") == "Apple"

def test_apple_bilinternet_variant():
    assert clean_description("APPLE.COM/BILINTERNET CHARGE") == "Apple"

def test_wholefds_expands():
    assert clean_description("WHOLEFDS MKT") == "Whole Foods"

def test_trader_joes():
    assert clean_description("TRADER JOE'S #123") == "Trader Joe's"


# ── Generic — payment-method prefix stripping ────────────────────────────────

def test_aplpay_prefix():
    assert clean_description("AplPay CORNER BAKERY") == "Corner Bakery"

def test_aplpay_all_caps():
    assert clean_description("APLPAY CORNER BAKERY") == "Corner Bakery"

def test_sq_prefix():
    assert clean_description("SQ *BLUE BOTTLE COFF") == "Blue Bottle Coff"

def test_tst_prefix():
    assert clean_description("TST* CHIPOTLE") == "Chipotle"

def test_paypal_prefix():
    assert clean_description("PP*GAME PURCHASE") == "Game Purchase"

def test_sp_prefix_before_letter():
    # "SP " followed by a letter → Shopify prefix, strip it
    assert clean_description("SP ALDO") == "Aldo"

def test_sp_prefix_before_number_untouched():
    # "SP 123" — not a Shopify prefix (followed by digit), leave it
    result = clean_description("SP 123 STORE")
    assert result != "Aldo"          # must not strip "SP 123"


# ── Generic — POS terminal prefix stripping ──────────────────────────────────

def test_par_prefix_stripped():
    assert clean_description("PAR*LOCAL DINER") == "Local Diner"

def test_cpi_prefix_stripped():
    result = clean_description("CPI*SUNRISE CAFE")
    assert result == "Sunrise Cafe"

def test_ctlp_prefix_stripped():
    result = clean_description("CTLP*SUNRISE CAFE")
    assert result == "Sunrise Cafe"


# ── Generic — trailing city / address noise ──────────────────────────────────

def test_trailing_digit_city_stripped():
    assert clean_description("SQ *SHELL GAS 3372CHICAGO") == "Shell Gas"

def test_trailing_hash_city_stripped():
    result = clean_description("SQ *CORNER SHOP #MADISON")
    assert "MADISON" not in result.upper()

def test_trailing_city_with_space():
    result = clean_description("SQ *CORNER SHOP CHICAGO")
    assert "CHICAGO" not in result.upper()


# ── Generic — title case and apostrophe fix ───────────────────────────────────

def test_title_case_applied():
    assert clean_description("SQ *CORNER CAFE") == "Corner Cafe"

def test_apostrophe_not_uppercased():
    # Apostrophes in generic-path results must not produce "Foo'S"
    result = clean_description("SQ *CASEY'S GENERAL STORE")
    assert result == "Casey's General Store"


# ── New merchant dictionary entries ──────────────────────────────────────────

def test_ianspizza_dot_com():
    assert clean_description("ianspizza.com") == "Ian's Pizza"

def test_nafnafgrill_no_spaces():
    assert clean_description("Nafnafgrill") == "Naf Naf Grill"

def test_fedex_with_trailing_id():
    assert clean_description("Fedex Offic416000041") == "FedEx"

def test_conrads_with_city():
    assert clean_description("Conrads - Madiso") == "Conrads Grill"

def test_paypal_ach():
    assert clean_description("Ach:Paypal -Inst Xfer") == "PayPal"

def test_subway_with_store_number():
    assert clean_description("Subway 39688") == "Subway"

def test_starbucks_with_store():
    assert clean_description("Starbucks Store 0230") == "Starbucks"

def test_uber_pending():
    assert clean_description("UBR* PENDING.UBER.CO") == "Uber"


# ── Specific bank patterns ────────────────────────────────────────────────────

def test_transfer_from_checking():
    assert clean_description("Web Branch:Tfr From Ck") == "Transfer from Checking"

def test_transfer_to_checking():
    assert clean_description("Web Branch:Tfr To Ck") == "Transfer to Checking's"

def test_transfer_from_savings():
    assert clean_description("Web Branch:Tfr From Sv") == "Transfer from Savings"

def test_university_payroll():
    assert clean_description("Ach:University Of Wi -Payroll") == "Paycheck"

def test_university_direct_deposit():
    assert clean_description("Ach:University Of Wi -Dir Dep") == "Paycheck"

def test_atm_deposit():
    assert clean_description("Atm 7884:Deposit Uw Credit 03/17/26 22:16") == "ATM Deposit"


# ── Zelle and Venmo patterns ──────────────────────────────────────────────────

def test_zelle_middle_initial_stripped():
    assert clean_description("Web Branch:Zelle MANAN A PAT 800-533-6773") == "Zelle — Manan Patel"

def test_zelle_phone_stripped_resolves_to_contact():
    assert clean_description("Web Branch:Zelle MANAN PATE 800-533-6773") == "Zelle — Manan Patel"

def test_zelle_full_name_with_phone():
    assert clean_description("Web Branch:Zelle MANAN PATEL 800-533-6773") == "Zelle — Manan Patel"

def test_zelle_middle_initial_single_name():
    assert clean_description("Web Branch:Zelle Dhairya A S 800-533-6773") == "Zelle — Dhairya"

def test_zelle_full_name_match():
    assert clean_description("Web Branch:Zelle Rhea Kartik 800-533-6773") == "Zelle — Rhea Kartik"

def test_zelle_truncated_first_name_only():
    assert clean_description("Web Branch:Zelle Aadvik Cha 800-533-6773") == "Zelle — Aadvik"

def test_zelle_truncated_single_name():
    assert clean_description("Web Branch:Zelle Dhairya Se 800-533-6773") == "Zelle — Dhairya"

def test_zelle_full_two_word_name():
    assert clean_description("Web Branch:Zelle Aryan Jaymi 800-533-6773") == "Zelle — Aryan Jaymi"

def test_zelle_unknown_person_fallback():
    assert clean_description("Web Branch:Zelle Unknown Person 800-533-6773") == "Zelle — Unknown Person"

def test_zelle_no_name():
    assert clean_description("Web Branch:Zelle") == "Zelle"

def test_venmo_payment():
    assert clean_description("Ach:Venmo -Payment") == "Venmo"


# ── New merchant dictionary entries ──────────────────────────────────────────

def test_sephora():
    assert clean_description("Sephora.Com 877-Sephora") == "Sephora"

def test_nike():
    assert clean_description("Nike Inc E-Commerce") == "Nike"

def test_coach_usa():
    assert clean_description("Coach Usa 8669126224") == "Coach USA"

def test_uniqlo():
    assert clean_description("Uniqlo Usa Llc") == "Uniqlo"

def test_wiscard():
    assert clean_description("Wiscard Web") == "Wiscard Deposit"

def test_arbys():
    assert clean_description("Arbys 6804") == "Arby's"


# ── Venmo phone number pattern ────────────────────────────────────────────────

def test_venmo_phone_number():
    assert clean_description("Venmo 8558124430") == "Venmo"


# ── Card Purchase extraction ──────────────────────────────────────────────────

def test_card_purchase_madistan():
    assert clean_description("Card Purchase 09/27 Tst Madistan Madison Wi Card 7275") == "Madistan"

def test_card_purchase_mooyah():
    assert clean_description("Card Purchase 10/11 Mooyah 238 Madison Wi Card 7275") == "Mooyah"

def test_card_purchase_chipotle():
    assert clean_description("Card Purchase 10/18 Chipotle 0312 Madison Wi Card 7275") == "Chipotle"
