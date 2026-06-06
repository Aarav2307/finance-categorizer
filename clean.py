"""
Display-name cleaning for raw bank transaction descriptions.

clean_description(raw) is the only public entry point.
Raw descriptions are never modified — this produces display-only names.
"""

import re

KNOWN_MERCHANTS: dict[str, str] = {
    "CANTEEN":        "Canteen Vending",
    "UBER EATS":      "Uber Eats",
    "UBEREATS":       "Uber Eats",
    "PENDING.UBER":   "Uber",
    "UBR*":           "Uber",
    "7-ELEVEN":       "7-Eleven",
    "7 ELEVEN":       "7-Eleven",
    "OPENAI":         "ChatGPT",
    "APPLE.COM/BIL":  "Apple",
    "AMAZON":         "Amazon",
    "AMZN":           "Amazon",
    "NORTH FACE":     "The North Face",
    "RAISING CANE":   "Raising Cane's",
    "IAN'S PIZZA":    "Ian's Pizza",
    "IANSPIZZA":      "Ian's Pizza",
    "NAFNAFGRILL":    "Naf Naf Grill",
    "NAF NAF":        "Naf Naf Grill",
    "TACO BELL":      "Taco Bell",
    "PINKUS MARKET":  "Pinkus Market",
    "MOKA":           "Moka",
    "STOP N SHOP":    "Stop N Shop",
    "NETFLIX":        "Netflix",
    "SPOTIFY":        "Spotify",
    "STARBUCKS":      "Starbucks",
    "HULU":           "Hulu",
    "DOORDASH":       "DoorDash",
    "GRUBHUB":        "Grubhub",
    "CONRADS":        "Conrads Grill",
    "CHIPOTLE":       "Chipotle",
    "SUBWAY":         "Subway",
    "FEDEX":          "FedEx",
    "SEPHORA":        "Sephora",
    "COACH USA":      "Coach USA",
    "COACH":          "Coach USA",
    "UNIQLO":         "Uniqlo",
    "MOOYAH":         "Mooyah",
    "MADISTAN":       "Madistan",
    "WISCARD":        "Wiscard Deposit",
    "ARBYS":          "Arby's",
    "NIKE":           "Nike",
    "LYFT":           "Lyft",
    "INSTACART":      "Instacart",
    "PAYPAL":         "PayPal",
    "TARGET":         "Target",
    "WALMART":        "Walmart",
    "WHOLEFDS":       "Whole Foods",
    "TRADER JOE":     "Trader Joe's",
}

# Sorted longest-first so the most specific key wins when multiple match.
_KNOWN_KEYS = sorted(KNOWN_MERCHANTS, key=len, reverse=True)

KNOWN_ZELLE_CONTACTS = [
    "Aadvik",
    "Arin Bajaj",
    "Aryan Jaymi",
    "Cxc",
    "Dhairya",
    "Kritin Kaushik",
    "Madhu Shriv",
    "Mahek",
    "Manan Patel",
    "Medhavi",
    "Naisha Chadha",
    "Rhea Kartik",
    "Shrushti",
    "Tanuj Nimit",
    "Zarak",
    "Zayee",
]

# Longest alternatives first so the regex engine finds them before shorter ones.
_CITIES_PAT = (
    r'(?:SAN FRANCISCO|LOS ANGELES|NEW YORK|PHILADELPHIA|'
    r'FITCHBURG|CHARLOTTE|PORTLAND|HOUSTON|PHOENIX|'
    r'MADISON|CHICAGO|SEATTLE|AUSTIN|BOSTON|MIAMI|DALLAS|DENVER|ATLANTA)'
)


def _remove_middle_initials(name: str) -> str:
    """Strip single-letter tokens (middle initials) from a name string."""
    tokens = name.upper().split()
    return " ".join(t for t in tokens if len(t) > 1)


def clean_description(raw: str) -> str:
    upper = raw.upper()

    # ── Layer 1: known merchant dictionary ────────────────────────────────────
    for key in _KNOWN_KEYS:
        if key in upper:
            return KNOWN_MERCHANTS[key]

    # ── Specific patterns (bank-specific descriptions with no merchant name) ───
    if re.match(r'Web Branch:Zelle', raw, re.IGNORECASE):
        name_part = re.sub(r'^Web Branch:Zelle\s*', '', raw, flags=re.IGNORECASE).strip()
        name_part = re.sub(r'\s*\d{3}-\d{3}-\d{4}\s*$', '', name_part).strip()

        if not name_part:
            return "Zelle"

        bank_name_clean = _remove_middle_initials(name_part)

        best_match = None
        best_len = 0
        for contact in KNOWN_ZELLE_CONTACTS:
            contact_clean = _remove_middle_initials(contact)
            if bank_name_clean.startswith(contact_clean) or contact_clean.startswith(bank_name_clean):
                if len(contact_clean) > best_len:
                    best_match = contact
                    best_len = len(contact_clean)

        return f"Zelle — {best_match if best_match else name_part.title()}"

    if re.match(r'Web Branch:Tfr From Ck', raw, re.IGNORECASE):
        return "Transfer from Checking"
    if re.match(r'Web Branch:Tfr To Ck', raw, re.IGNORECASE):
        return "Transfer to Checking's"
    if re.match(r'Web Branch:Tfr From Sv', raw, re.IGNORECASE):
        return "Transfer from Savings"
    if re.match(r'Ach:University Of Wi', raw, re.IGNORECASE):
        return "Paycheck"
    if re.match(r'Ach:Venmo', raw, re.IGNORECASE):
        return "Venmo"
    if re.match(r'^Venmo\s+\d+', raw, re.IGNORECASE):
        return "Venmo"
    if re.match(r'Atm\s*\d+:Deposit', raw, re.IGNORECASE):
        return "ATM Deposit"

    card_match = re.match(
        r'Card Purchase\s+\d{2}/\d{2}\s+(.+?)\s+[A-Za-z]+\s+[A-Z]{2}\s+Card\s+\d+',
        raw, re.IGNORECASE,
    )
    if card_match:
        return clean_description(card_match.group(1).strip())

    # Wells Fargo POS Purchase — "POS Purchase - MM/DD Mach ID XXXX MERCHANT CITY ST ZIP"
    # "Purchase" may have watermark letters inserted, e.g. "POS PMMurchase"
    if re.match(r'POS\s+P[A-Z]*urchase', raw, re.IGNORECASE):
        cleaned = re.sub(r'^POS\s+P[A-Z]*urchase\s*-\s*\d{2}/\d{2}\s+Mach\s+ID\s+\S+\s*', '', raw, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+\S+(?:,\s*)?\s+(?:USA?|[A-Z]{2})\s+\d{5}.*$', '', cleaned).strip()
        return cleaned.title() if cleaned else 'POS Purchase'

    # Wells Fargo Bill Pay — "Bill Pay - Merchant On-Line …"
    if re.match(r'Bill Pay', raw, re.IGNORECASE):
        m = re.match(r'Bill Pay\s*-\s*(.+?)\s+(?:On-Line|Online|\d{4})', raw, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
        m = re.match(r'Bill Pay\s*-\s*(.+)', raw, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
        return 'Bill Pay'

    if re.match(r'ATM Withdrawal', raw, re.IGNORECASE):
        return 'ATM Withdrawal'

    # ── Layer 2: generic stripping ────────────────────────────────────────────
    # Strip any remaining "Web Branch:" prefix before generic processing
    s = re.sub(r'^Web Branch:', '', raw, flags=re.IGNORECASE).strip()

    # Step 1 — strip payment-method prefixes at the start
    s = re.sub(r'^(?:AplPay|APLPAY)\s+', '', s)
    s = re.sub(r'^SP\s+(?=[A-Za-z])', '', s)          # Shopify, but not "SP123"
    s = re.sub(r'^(?:PP\*|PAYPAL\s*\*\s*)', '', s, flags=re.I)
    s = re.sub(r'^SQ\s*\*\s*', '', s, flags=re.I)
    s = re.sub(r'^TST\*\s*', '', s, flags=re.I)

    # Step 2 — strip terminal/POS prefixes (2–6 uppercase letters + *)
    s = re.sub(r'^[A-Z]{2,6}\*', '', s)

    # Step 3 — strip URLs and phone numbers
    s = re.sub(r'\s+(?:https?://\S+|\S+\.\S+/\S*)', '', s, flags=re.I)
    s = re.sub(r'\s+\S+\.\w{2,6}\b', '', s, flags=re.I)
    s = re.sub(r'\s*\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}', '', s)
    s = re.sub(r'\s*\(\d{3}\)\d{3}-\d{4}', '', s)

    # Step 4 — strip trailing address numbers and city names
    s = re.sub(r'\s*\d+[A-Za-z]+\s*$', '', s)         # "3372CHICAGO", "300MADISON"
    s = re.sub(r'\s*#[A-Za-z]+\s*$', '', s)            # "#MADISON"
    s = re.sub(r'\s*' + _CITIES_PAT + r'\s*$', '', s, flags=re.I)

    # Step 5 — final cleanup
    s = s.strip(' \t-–—')                    # leading/trailing hyphens/dashes
    s = re.sub(r'\s*\*\s*', ' ', s).strip()            # remaining asterisks → space
    s = re.sub(r'\s+', ' ', s).strip()
    # Title case; fix apostrophe: "Cane'S" → "Cane's"
    s = s.title()
    s = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), s)

    return s
