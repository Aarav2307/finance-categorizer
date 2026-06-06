"""
Tests the UWCU and Chase text parsing logic against real statement text.
Run with: python test_pdf_parser.py
"""
import re

# ── copied from main.py ───────────────────────────────────────────────────────

def _parse_amount(s: str):
    if not s:
        return None
    s = s.strip().replace(',', '').replace('$', '').replace('\xa0', '').replace(' ', '')
    if not s or s == '-':
        return None
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    if s.endswith('-'):
        s = '-' + s[:-1]
    try:
        return float(s)
    except ValueError:
        return None

# ── regexes under test ────────────────────────────────────────────────────────

LINE_RE = re.compile(
    r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2}-?)\s+[\d,]+\.\d{2}\s*$'
)
CONT_RE = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+?)\s*$')

# ── UWCU sample (exact spacing from the PDF) ──────────────────────────────────
# Key patterns present:
#   - leading whitespace before every line
#   - single space between MM/DD and description
#   - 2+ spaces before amount column
#   - trailing '-' for debits
#   - continuation lines: "  MM/DD/YY   MERCHANT NAME"
#   - "ID: ..." lines that must be ignored
#   - "Balance Forward" line to skip

# Exact pdfplumber output (no leading whitespace, single-space separated)
UWCU_TEXT = """\
Date_Activity______________________________________________Amount______Balance
08/31 Balance Forward --------------------------------------------> 261.04
09/02 ACH:PURAB AGARWAL -ZELLE 2.00- 259.04
09/03 Web Branch:Zelle CXC 800-533-6773 2.00 261.04
09/03 Web Branch:Zelle Aadvik Cha 800-533-6773 5.50- 255.54
09/04 DEBITCARD 5527:PURCHASE CHARLOTTE NC 1.75- 253.79
09/03/25 CTLP*CANTEEN VENDING
09/04 Web Branch:WIRE TRANSFER 9,570.00 9,823.79
09/04 Web Branch:WIRE TRANSFER FEE 15.00- 9,808.79
09/04 Web Branch:TFR TO SV 089781301 9,600.00- 208.79
09/04 ACH:FID BKG SVC LLC -ACH 800.00 1,008.79
ID: Z19823841 4AO09
09/04 Web Branch:TFR TO SV 089781301 800.00- 208.79
09/05 PROMO: CHECKING BONUS 50.00 258.79
09/05 Web Branch:Zelle Aadvik Chat 800-533-6773 14.50 273.29
09/06 DEBITCARD 5527:PURCHASE DOORDASH.COM CA 28.55- 244.74
09/06/25 DD *DOORDASH DOMINOS
09/08 Web Branch:Zelle Aadvik Cha 800-533-6773 5.00- 239.74
09/08 DEBITCARD 5527:PURCHASE Madison WI 3.19- 236.55
09/06/25 610 State Street
09/09 DEBITCARD 5527:PURCHASE MADISON WI 3.96- 225.09
09/09/25 STARBUCKS STORE 0230
09/14 Web Branch:Zelle Aadvik Cha 800-533-6773 19.00- 207.09
09/15 DEBITCARD 5527:PURCHASE MADISON WI 11.65- 195.44
09/14/25 RAISING CANES 0601
09/24 ATM 5527:WITHDRAWAL UW CREDIT 09/24/25 13:23 20.00- 86.49
662 STATE STREET MADISON WI
09/24 Web Branch:TFR FROM SV 089781301 89.51 176.00
"""

def parse_uwcu(text):
    txns = []
    pending = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        cont = CONT_RE.match(line)
        if cont and pending is not None:
            merchant = cont.group(2).strip()
            if merchant and not merchant.lower().startswith('id:'):
                pending['description'] = merchant
            txns.append(pending)
            pending = None
            continue

        if pending is not None:
            txns.append(pending)
            pending = None

        m = LINE_RE.match(line)
        if not m:
            continue

        desc   = m.group(2).strip()
        amount = _parse_amount(m.group(3))

        if not desc or 'balance' in desc.lower() or amount is None:
            continue

        pending = {"description": desc, "amount": amount}

    if pending is not None:
        txns.append(pending)
    return txns

# ── run tests ─────────────────────────────────────────────────────────────────

print("=== UWCU Parser Test ===\n")
results = parse_uwcu(UWCU_TEXT)
for t in results:
    print(f"  {t['amount']:>10.2f}  {t['description']}")

print(f"\nTotal transactions found: {len(results)}")

# Expected:
EXPECTED = [
    ("ACH:PURAB AGARWAL -ZELLE", -2.00),
    ("Web Branch:Zelle CXC 800-533-6773", 2.00),
    ("Web Branch:Zelle Aadvik Cha 800-533-6773", -5.50),
    ("CTLP*CANTEEN VENDING", -1.75),   # description replaced by continuation line
    ("Web Branch:WIRE TRANSFER", 9570.00),
    ("Web Branch:WIRE TRANSFER FEE", -15.00),
    ("Web Branch:TFR TO SV 089781301", -9600.00),
    ("ACH:FID BKG SVC LLC -ACH", 800.00),  # ID line should be ignored
    ("Web Branch:TFR TO SV 089781301", -800.00),
    ("PROMO: CHECKING BONUS", 50.00),
    ("Web Branch:Zelle Aadvik Chat 800-533-6773", 14.50),
    ("DD *DOORDASH DOMINOS", -28.55),
    ("Web Branch:Zelle Aadvik Cha 800-533-6773", -5.00),
    ("610 State Street", -3.19),     # description replaced by continuation
    ("STARBUCKS STORE 0230", -3.96),
    ("Web Branch:Zelle Aadvik Cha 800-533-6773", -19.00),
    ("RAISING CANES 0601", -11.65),
    ("ATM 5527:WITHDRAWAL UW CREDIT 09/24/25 13:23", -20.00),
    ("Web Branch:TFR FROM SV 089781301", 89.51),
]

print("\n=== Validation ===")
ok = True
for i, (exp_desc, exp_amt) in enumerate(EXPECTED):
    if i >= len(results):
        print(f"  MISSING [{i}]: {exp_desc} {exp_amt}")
        ok = False
        continue
    r = results[i]
    amt_ok  = abs(r['amount'] - exp_amt) < 0.001
    if not amt_ok:
        print(f"  AMOUNT MISMATCH [{i}]: got {r['amount']}, expected {exp_amt}  | desc: {r['description']!r}")
        ok = False

if len(results) != len(EXPECTED):
    print(f"  COUNT MISMATCH: got {len(results)}, expected {len(EXPECTED)}")
    ok = False

if ok:
    print("  All checks passed!")

# ── Chase text-line format test ───────────────────────────────────────────────
# Chase amounts use leading '-' for debits, no trailing '-'.
# No continuation lines. Multi-line descriptions wrap but the line with
# the amount+balance is the important one.

CHASE_TEXT = """\
DATE DESCRIPTION AMOUNT BALANCE
Beginning Balance  $74.24
09/26 Card Purchase 09/26 Raising Canes 0601 Madison WI Card 7275  -12.97  61.27
09/29 Card Purchase 09/27 Tst*Madistan Madison WI Card 7275  -14.49  46.78
10/01 Card Purchase 09/30 Uw Gordon Dining Madison WI Card 7275  -1.89  44.89
10/01 Card Purchase 10/01 Ianspizza.Com 178-15833699 WI Card 7275  -14.00  30.89
10/06 Book Transfer Credit B/O: Indusind Bank  9,570.00  9,600.89
10/06 Card Purchase 10/03 Uw Madison Wisc Union Madison WI Card 7275  -4.85  9,596.04
10/06 International Incoming Wire Fee  -15.00  9,575.61
10/07 $125 For New Checking  125.00  9,700.61
10/14 Card Purchase 10/11 Mooyah 238 Madison WI Card 7275  -4.46  9,711.15
10/14 Uwmsnbursaroffc 6082659738 0006708601 Web ID: Msne030800  -9,558.49  152.66
10/20 Card Purchase 10/18 Chipotle 0312 Madison WI Card 7275  -13.87  138.79
10/20 Card Purchase 10/20 Ianspizza.Com 178-15833699 WI Card 7275  -6.50  128.04
10/20 Card Purchase 10/20 Ianspizza.Com 178-15833699 WI Card 7275  -5.50  122.54
10/21 Card Purchase 10/20 Cpi*Canteen Vending M 800-628-8363 WI Card 7275  -2.50  120.04
10/22 Card Purchase 10/21 Raising Canes 0601 Madison WI Card 7275  -11.65  108.39
Ending Balance  $108.39
"""

print("\n=== Chase Text Parser Test ===\n")
chase_results = parse_uwcu(CHASE_TEXT)  # same parser handles both formats
for t in chase_results:
    print(f"  {t['amount']:>10.2f}  {t['description']}")
print(f"\nTotal: {len(chase_results)} transactions")
assert len(chase_results) == 15, f"Expected 15, got {len(chase_results)}"
assert chase_results[0]['amount'] == -12.97
assert chase_results[4]['amount'] == 9570.00
assert chase_results[10]['amount'] == -13.87
print("  All checks passed!")
