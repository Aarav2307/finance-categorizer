import hashlib, io, csv, json, re
from datetime import datetime, timedelta, timezone, date as date_type
from pathlib import Path
import pdfplumber
from recurring import detect_recurring, normalize_merchant

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
from jose import JWTError, jwt

from categorize import (
    normalize, match_rules, categorize as run_llm,
    load_cache, save_cache, get_category_from_cache,
    ALLOWED, CACHE_PATH, CONFIDENCE_THRESHOLD,
)
from clean import clean_description

# ── Auth config ───────────────────────────────────────────────────────────────
SECRET_KEY = "change-this-secret-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
bearer_scheme = HTTPBearer()

USERS_PATH = Path(__file__).parent / "users.json"
HISTORY_DIR = Path(__file__).parent / "history"
ZELLE_NAMES_PATH = Path(__file__).parent / "zelle_names.json"
ACCOUNTS_PATH        = Path(__file__).parent / "accounts.json"
RECURRING_CACHE_PATH = Path(__file__).parent / "recurring_cache.json"
RECURRING_CACHE_TTL  = 3600  # seconds

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── User storage ──────────────────────────────────────────────────────────────

def load_users() -> list:
    try:
        with open(USERS_PATH) as f:
            return json.load(f).get("users", [])
    except FileNotFoundError:
        return []

def save_users(users: list):
    with open(USERS_PATH, "w") as f:
        json.dump({"users": users}, f, indent=2)

def load_zelle_names() -> dict:
    try:
        with open(ZELLE_NAMES_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_zelle_names(names: dict):
    with open(ZELLE_NAMES_PATH, "w") as f:
        json.dump(names, f, indent=2)

def load_accounts() -> list:
    try:
        with open(ACCOUNTS_PATH) as f:
            return json.load(f).get("accounts", [])
    except FileNotFoundError:
        return []

def save_accounts(accounts: list):
    with open(ACCOUNTS_PATH, "w") as f:
        json.dump({"accounts": accounts}, f, indent=2)

def seed_default_accounts():
    """Ensure UWCU and Chase exist in the accounts store on first run."""
    accounts = load_accounts()
    existing = {a["name"].lower() for a in accounts}
    defaults = [{"name": "UWCU", "type": "bank"}, {"name": "Chase", "type": "bank"}]
    added = [d for d in defaults if d["name"].lower() not in existing]
    if added:
        save_accounts(accounts + added)

seed_default_accounts()

# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def require_auth(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> str:
    """Dependency: verifies the Bearer token and returns the user's email."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
        return email
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

# ── Auth endpoints (no auth required) ─────────────────────────────────────────

class RegisterPayload(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    password: str

@app.post("/register")
def register(payload: RegisterPayload):
    users = load_users()
    if any(u["email"].lower() == payload.email.lower() for u in users):
        raise HTTPException(400, "An account with that email already exists")
    users.append({
        "email": payload.email.lower(),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "phone": payload.phone,
        "hashed_password": hash_password(payload.password),
    })
    save_users(users)
    # Auto-login: return token immediately after registration
    token = create_token(payload.email.lower())
    return {
        "token": token,
        "user": {"email": payload.email, "first_name": payload.first_name, "last_name": payload.last_name},
    }


class LoginPayload(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(payload: LoginPayload):
    users = load_users()
    user = next((u for u in users if u["email"] == payload.email.lower()), None)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(401, "Incorrect email or password")
    token = create_token(payload.email.lower())
    return {
        "token": token,
        "user": {"email": user["email"], "first_name": user["first_name"], "last_name": user["last_name"]},
    }

# ── PDF parsing ───────────────────────────────────────────────────────────────

def _parse_amount(s: str) -> float | None:
    """Convert a bank amount string to float. Handles $, commas, (neg) notation, and trailing - (UWCU)."""
    if not s:
        return None
    s = s.strip().replace(',', '').replace('$', '').replace('\xa0', '').replace(' ', '')
    if not s or s == '-':
        return None
    # Parentheses mean negative: (14.50) → -14.50
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    # Trailing minus means negative (UWCU debit style): 14.50- → -14.50
    if s.endswith('-'):
        s = '-' + s[:-1]
    try:
        return float(s)
    except ValueError:
        return None

def _is_amount_col(values: list) -> bool:
    """True if >70% of non-empty cells in this column look like numbers."""
    non_empty = [v for v in values if v and str(v).strip()]
    if len(non_empty) < 2:
        return False
    parseable = sum(1 for v in non_empty if _parse_amount(str(v)) is not None)
    return parseable / len(non_empty) > 0.7

def _parse_table(table: list) -> list[dict]:
    """Extract transactions from a single pdfplumber table (Chase-style)."""
    if not table or len(table) < 2:
        return []

    headers = [str(h).strip().lower() if h else '' for h in table[0]]
    rows = table[1:]
    txns = []

    # Identify columns by header keyword
    desc_idx = amt_idx = debit_idx = credit_idx = date_idx = None
    for i, h in enumerate(headers):
        if any(k in h for k in ('description', 'transaction', 'merchant', 'details', 'memo', 'narration', 'particulars')):
            desc_idx = i
        if any(k in h for k in ('amount', 'total')):
            amt_idx = i
        if any(k in h for k in ('debit', 'withdrawal', 'dr')):
            debit_idx = i
        if any(k in h for k in ('credit', 'deposit', 'cr')):
            credit_idx = i
        if any(k in h for k in ('date', 'posted', 'posting')):
            date_idx = i

    # Fall back to column-content detection
    if desc_idx is None or (amt_idx is None and debit_idx is None):
        col_vals = [[] for _ in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_vals[i].append(str(cell) if cell else '')

        amount_cols = [i for i, v in enumerate(col_vals) if _is_amount_col(v)]
        text_cols   = [i for i in range(len(headers)) if i not in amount_cols]

        if not amount_cols or not text_cols:
            return []

        desc_idx = max(text_cols, key=lambda i: sum(len(v) for v in col_vals[i]))

        if len(amount_cols) >= 2:
            debit_idx, credit_idx = amount_cols[-2], amount_cols[-1]
            amt_idx = None
        else:
            amt_idx = amount_cols[-1]

    for row in rows:
        if desc_idx >= len(row):
            continue
        desc = str(row[desc_idx] or '').strip()
        # Skip balance summary rows
        if not desc or desc.lower() in ('', 'none', 'nan') or 'balance' in desc.lower():
            continue

        amount = None
        if amt_idx is not None and amt_idx < len(row):
            amount = _parse_amount(str(row[amt_idx] or ''))
        elif debit_idx is not None and credit_idx is not None:
            debit  = _parse_amount(str(row[debit_idx]  or '')) if debit_idx  < len(row) else None
            credit = _parse_amount(str(row[credit_idx] or '')) if credit_idx < len(row) else None
            if debit:
                amount = -abs(debit)
            elif credit:
                amount = abs(credit)

        date_str = str(row[date_idx]).strip() if date_idx is not None and date_idx < len(row) and row[date_idx] else None
        if amount is not None:
            txns.append({"description": desc, "amount": amount, "date": date_str})

    return txns

# Matches transaction lines for both UWCU and Chase text-based extraction.
# pdfplumber strips leading whitespace, so lines start directly with MM/DD.
#   UWCU:  "MM/DD description... 2.00- 259.04"   (trailing - = debit)
#   Chase: "MM/DD Description... -12.97 61.27"   (leading - = debit)
# Single spaces between all fields; lazy .+? with backtracking finds the split.
_TXN_LINE_RE = re.compile(
    r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\d,]+\.\d{2}-?)\s+[\d,]+\.\d{2}\s*$'
)
# Matches UWCU continuation lines: "MM/DD/YY MERCHANT NAME"
# Distinguished from main lines because date is MM/DD/YY (8 chars) not MM/DD (5 chars).
_UWCU_CONT_RE = re.compile(r'^(\d{2}/\d{2}/\d{2})\s+(.+?)\s*$')

def _parse_text_statement(text: str) -> list[dict]:
    """
    Parse text-based bank statements (UWCU and Chase text-extracted lines).
    Both formats share: [whitespace] MM/DD  DESCRIPTION  AMOUNT  BALANCE
    UWCU uses trailing '-' for debits; Chase uses leading '-'.
    UWCU also has continuation lines (MM/DD/YY MERCHANT) that replace the description.
    """
    txns = []
    lines = text.splitlines()
    pending = None

    for line in lines:
        line = line.rstrip()

        cont = _UWCU_CONT_RE.match(line)
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

        m = _TXN_LINE_RE.match(line)
        if not m:
            continue

        desc   = m.group(2).strip()
        amount = _parse_amount(m.group(3))

        if not desc or 'balance' in desc.lower() or amount is None:
            continue

        pending = {"description": desc, "amount": amount, "date": m.group(1)}

    if pending is not None:
        txns.append(pending)

    return txns

# ── Wells Fargo statement parser ──────────────────────────────────────────────

_WF_MONTH_MAP: dict[str, int] = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _is_wells_fargo(text: str) -> bool:
    return bool(re.search(r'WELLS\s+FARGO', text, re.IGNORECASE))


def _parse_wells_fargo_statement(text: str) -> list[dict]:
    lines = text.splitlines()

    # Extract statement date (e.g. "Statement Date: May 3, 2002")
    stmt_year  = date_type.today().year
    stmt_month = date_type.today().month
    for line in lines:
        m = re.search(r'Statement Date:\s*(\w+)\s+(\d{1,2}),?\s+(\d{4})', line, re.IGNORECASE)
        if m:
            mname = m.group(1).lower()
            if mname in _WF_MONTH_MAP:
                stmt_month = _WF_MONTH_MAP[mname]
            stmt_year = int(m.group(3))
            break

    # Extract account-holder surnames from the header block (before "Account Number:").
    # Filter single-char tokens to ignore watermark letters ("ANNIE SMITH L" → "smith").
    surnames: set[str] = set()
    for line in lines:
        if re.search(r'Account Number:', line, re.IGNORECASE):
            break
        stripped = line.strip()
        m = re.match(r'^([A-Z]+(?:\s+[A-Z]+)+)\s*$', stripped)
        if m:
            parts = [p for p in stripped.split() if len(p) > 1]
            if parts:
                surnames.add(parts[-1].lower())

    def _full_date(mm_dd: str) -> str:
        mo = int(mm_dd[:2])
        year = stmt_year - 1 if mo > stmt_month else stmt_year
        return f"{mm_dd}/{year}"

    _AMT_TAIL = re.compile(r'^(.*?)\s+\$?([\d,]+\.\d{2})\s*$')

    def _split_last_amount(s: str) -> tuple[str, str | None]:
        m = _AMT_TAIL.match(s)
        return (m.group(1).strip(), m.group(2)) if m else (s.strip(), None)

    def _clean_wf_desc(desc: str) -> str:
        if re.match(r'Bill Pay', desc, re.IGNORECASE):
            m = re.match(r'Bill Pay\s*-\s*(.+?)\s+(?:On-Line|Online|\d{4})', desc, re.IGNORECASE)
            if m:
                return m.group(1).strip().title()
            m = re.match(r'Bill Pay\s*-\s*(.+)', desc, re.IGNORECASE)
            if m:
                return m.group(1).strip().title()
            return "Bill Pay"
        if re.match(r'ATM Withdrawal', desc, re.IGNORECASE):
            return "ATM Withdrawal"
        return desc

    # State machine
    section: str | None = None   # 'deposits' | 'checks' | 'other_withdrawals'
    pending_date: str | None = None
    pending_desc: str | None = None
    transactions: list[dict] = []

    def flush(amount_str: str | None = None) -> None:
        nonlocal pending_date, pending_desc
        if pending_date is not None and amount_str is not None:
            amt = _parse_amount(amount_str)
            if amt is not None:
                desc = _clean_wf_desc(pending_desc or '')
                signed = abs(amt) if section == 'deposits' else -abs(amt)
                transactions.append({
                    'date':        _full_date(pending_date),
                    'description': desc,
                    'amount':      signed,
                })
        pending_date = None
        pending_desc = None

    _DATE_LINE  = re.compile(r'^(\d{2}/\d{2})\s+(.*)')
    _CHECKS_PAT = re.compile(r'(\d+)\*?\s+(\d{2}/\d{2})\s+([\d,]+\.\d{2})')
    # Suffix allowing 1-3 trailing uppercase letters (watermark noise, e.g. "Other withdrawals PP")
    _WM = r'(?:\s+[A-Z]{1,3})?\s*$'

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r'^[.\-]{10,}', line):
            continue

        # Section transitions; _WM allows trailing watermark noise
        if re.match(r'Deposits and interest' + _WM, line, re.IGNORECASE):
            flush(); section = 'deposits'; continue
        if re.match(r'Checks' + _WM, line, re.IGNORECASE):
            flush(); section = 'checks'; continue
        if re.match(r'Other withdrawals' + _WM, line, re.IGNORECASE):
            flush(); section = 'other_withdrawals'; continue
        if re.match(r'Total\b', line, re.IGNORECASE):
            flush(); section = None; continue

        if section is None:
            continue

        # Checks: "5254 04/08 21.33  5259 04/23 40.00" (two-column)
        if section == 'checks':
            for num, date_str, amt_str in _CHECKS_PAT.findall(line):
                amt = _parse_amount(amt_str)
                if amt is not None:
                    transactions.append({
                        'date':        _full_date(date_str),
                        'description': f'Check #{num}',
                        'amount':      -abs(amt),
                    })
            continue

        # Skip column headers
        if re.match(r'Date\s+Description\s+Amount', line, re.IGNORECASE):
            continue

        date_m = _DATE_LINE.match(line)
        if date_m:
            flush()
            date_str = date_m.group(1)
            rest = date_m.group(2).strip()
            text_part, amt_str = _split_last_amount(rest)
            if amt_str:
                # Single-line transaction
                pending_date = date_str
                pending_desc = text_part
                flush(amt_str)
            else:
                pending_date = date_str
                pending_desc = text_part
        else:
            # Continuation line
            if pending_date is None:
                continue
            text_part, amt_str = _split_last_amount(line)
            if amt_str is None:
                pending_desc = f"{pending_desc} {line}".strip() if pending_desc else line
                continue

            text_lower = text_part.lower()
            # "POS Purchase" may be corrupted by watermark letters (e.g. "POS PMMurchase")
            if pending_desc and re.match(r'POS\s+P[A-Z]*urchase', pending_desc, re.IGNORECASE):
                # Continuation is "Merchant City State Zip" — strip city/state/zip
                merchant = re.sub(
                    r'\s+\S+(?:,\s*)?\s+(?:USA?|[A-Z]{2})\s+\d{5}\b.*$', '', text_part
                ).strip()
                merchant = re.sub(r'(\s+\d+)+\s*$', '', merchant).strip()
                pending_desc = merchant or 'POS Purchase'
            elif pending_desc and re.match(r'ATM Withdrawal', pending_desc, re.IGNORECASE):
                pass  # keep pending_desc; _clean_wf_desc will reduce it to "ATM Withdrawal"
            elif text_lower in surnames or not text_lower:
                pass  # surname-only line — keep original description
            else:
                pending_desc = f"{pending_desc} {text_part}".strip() if pending_desc else text_part

            flush(amt_str)

    flush()
    return transactions


def parse_pdf(content: bytes) -> list[dict]:
    """
    Extract transactions from a bank-statement PDF.
    Detects Wells Fargo statements and routes them to a dedicated parser.
    For other formats, tries table extraction first (Chase-style), then falls
    back to text-line parsing (UWCU/Chase text-extracted format).
    """
    full_text_pages: list[str] = []
    txns: list[dict] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                txns.extend(_parse_table(table))
            full_text_pages.append(page.extract_text() or '')

    full_text = '\n'.join(full_text_pages)

    if _is_wells_fargo(full_text):
        return _parse_wells_fargo_statement(full_text)

    if len(txns) < 3:
        text_txns = _parse_text_statement(full_text)
        if text_txns:
            txns = text_txns

    return txns

# AMEX CSVs embed "           WI" style city+state suffix in the Description field.
_AMEX_STATE_RE = re.compile(r'\s{3,}[A-Z]{2}\s*$')

# Cities AMEX appends to merchant descriptions, sometimes with no space separator
# (e.g. "OPENAI *CHATGPT SUBSSAN FRANCISCO" = merchant "SUBS" + city "SAN FRANCISCO").
_AMEX_CITIES_RE = re.compile(
    r'\s*(SAN FRANCISCO|SAN JOSE|LOS ANGELES|NEW YORK|CHICAGO|SEATTLE|'
    r'AUSTIN|BOSTON|MIAMI|DALLAS|DENVER|ATLANTA|PORTLAND)\s*$',
    re.IGNORECASE,
)

def _clean_amex_desc(desc: str, city: str = '') -> str:
    """Strip trailing city/state from AMEX fixed-width description field."""
    s = _AMEX_STATE_RE.sub('', desc).rstrip()
    if city and len(city) >= 3:
        # Strip city when separated by 2+ spaces (original rule)
        s = re.sub(r'\s{2,}' + re.escape(city.upper()) + r'$', '', s, flags=re.I).rstrip()
    # Strip hardcoded cities — catches both spaced and zero-space concatenation
    # e.g. "CHATGPT SUBSSAN FRANCISCO" → "CHATGPT SUBS" (the "SAN" at end of "SUBS"+"SAN" aligns)
    s = _AMEX_CITIES_RE.sub('', s).rstrip()
    return s


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")  # strip BOM if present
    txns = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        fl = {k.strip().lower(): k for k in headers}  # case-insensitive key map

        # Detect AMEX format by its unique column names
        is_amex = 'city/state' in fl or 'appears on your statement as' in fl

        # Resolve column keys case-insensitively
        desc_key = fl.get('description')
        amt_key  = fl.get('amount')
        date_key = next((fl[k] for k in fl if k == 'date'), None)
        city_state_key = fl.get('city/state')

        if not desc_key or not amt_key:
            raise KeyError("'description' and 'amount' columns are required")

        for i, row in enumerate(reader):
            desc = row[desc_key].strip()

            if is_amex:
                # Parse "CITY\nSTATE" from the dedicated City/State column
                city_raw = ''
                if city_state_key:
                    parts = row[city_state_key].replace('\r', '').split('\n')
                    city_raw = parts[0].strip() if parts else ''
                desc = _clean_amex_desc(desc, city_raw)

            raw_amt = float(row[amt_key].replace(',', ''))
            # AMEX CSVs use positive = charge; our system uses negative = expense
            amount = -raw_amt if is_amex else raw_amt

            txns.append({
                "id": i,
                "desc": desc,
                "amount": amount,
                "date": row.get(date_key) if date_key else None,
            })
    except (KeyError, ValueError) as e:
        raise HTTPException(400, f"CSV parse error: {e}")
    return txns

# ── Credit card payment auto-detection ───────────────────────────────────────

_CC_PAYMENT_RE = re.compile(
    r'\b(AMEX|AMERICAN EXPRESS|CHASE CARD|CITI(?:BANK)?|DISCOVER|CAPITAL ONE|'
    r'CREDIT CARD PAYMENT|CARD PAYMENT|BARCLAYS|SYNCHRONY|APPLE CARD|WELLS FARGO CARD)\b',
    re.I,
)

def is_cc_payment(desc: str, account_type: str, amount: float) -> bool:
    return account_type == "bank" and amount < 0 and bool(_CC_PAYMENT_RE.search(desc))


# ── Display name helper ───────────────────────────────────────────────────────

def _add_display_names(transactions: list) -> None:
    for t in transactions:
        t['display_name'] = clean_description(t.get('description', ''))


# ── Recurring helpers ─────────────────────────────────────────────────────────

def enrich_with_recurring(transactions: list, ref: date_type) -> tuple[list, list]:
    """Tag each transaction with its recurring metadata and return (transactions, patterns)."""
    # Exclude Transfers from recurring detection to avoid CC payments skewing patterns
    non_transfers = [t for t in transactions if t.get('category') != 'Transfers']
    patterns = detect_recurring(non_transfers, reference_date=ref)
    pattern_map = {p['merchant_key']: p for p in patterns}
    for t in transactions:
        key = normalize_merchant(t.get('description', ''))
        if key in pattern_map:
            p = pattern_map[key]
            t['recurring_frequency'] = p['frequency']
            t['recurring_type']      = p['type']
        else:
            t.pop('recurring_frequency', None)
            t.pop('recurring_type', None)
    return transactions, patterns


# ── History helpers ───────────────────────────────────────────────────────────

def save_to_history(label: str, transactions: list, summary: list) -> str:
    HISTORY_DIR.mkdir(exist_ok=True)
    upload_id = datetime.now().strftime("%Y%m%d%H%M%S")
    entry = {
        "id": upload_id,
        "label": label,
        "uploaded_at": datetime.now().isoformat(),
        "transactions": transactions,
        "summary": summary,
    }
    with open(HISTORY_DIR / f"{upload_id}.json", "w") as f:
        json.dump(entry, f, indent=2)
    return upload_id

# ── Protected endpoints ───────────────────────────────────────────────────────

@app.post("/debug-pdf")
async def debug_pdf_upload(
    file: UploadFile = File(...),
    _: str = Depends(require_auth),
):
    """Temporary debug endpoint — returns raw pdfplumber output to help tune the parser."""
    content = await file.read()
    result = {"pages": []}
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables() or []
            text = page.extract_text() or ''
            result["pages"].append({
                "page": i,
                "tables": tables,
                "text_lines": text.splitlines(),
            })
    result["parsed_transactions"] = parse_pdf(content)
    return result


@app.post("/categorize")
async def categorize_upload(
    file: UploadFile = File(...),
    label: str = Form(default="Unlabeled"),
    account_name: str = Form(default=""),
    account_type: str = Form(default=""),
    _: str = Depends(require_auth),
):
    content = await file.read()
    ext = (file.filename or '').lower().split('.')[-1]

    if ext == 'pdf':
        try:
            raw = parse_pdf(content)
        except Exception as e:
            raise HTTPException(400, f"Could not extract transactions from PDF: {e}")
        if not raw:
            raise HTTPException(400, "No transactions found in PDF. The statement may use a format we can't read yet.")
        txns = [{"id": i, "desc": t["description"], "amount": t["amount"], "date": t.get("date")} for i, t in enumerate(raw)]
    elif ext == 'csv':
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "CSV must be UTF-8 encoded")
        txns = parse_csv(content)
    else:
        raise HTTPException(400, "Please upload a .csv or .pdf file")

    if not txns:
        raise HTTPException(400, "No transactions found in file")

    cache = load_cache(CACHE_PATH)
    results = {}
    llm_batch = []

    for t in txns:
        key = normalize(t["desc"])
        if key in cache:
            cat = get_category_from_cache(cache[key])
            results[t["id"]] = {"category": cat, "confidence": 1.0, "source": "cache"}
        else:
            cat = match_rules(t["desc"])
            if cat:
                results[t["id"]] = {"category": cat, "confidence": 1.0, "source": "rule"}
            else:
                llm_batch.append(t)

    if llm_batch:
        for r in run_llm(llm_batch):
            cat = r["category"] if r["category"] in ALLOWED else "Other"
            results[r["id"]] = {"category": cat, "confidence": r["confidence"], "source": "llm"}

    transactions = []
    totals = {}
    for t in txns:
        r = results.get(t["id"], {"category": "Other", "confidence": 0.0, "source": "llm"})
        category = r["category"]
        auto_transfer = False
        if is_cc_payment(t["desc"], account_type, t["amount"]):
            category = "Transfers"
            auto_transfer = True
        txn = {
            "id": t["id"],
            "description": t["desc"],
            "amount": t["amount"],
            "date": t.get("date"),
            "category": category,
            "confidence": r["confidence"],
            "source": "auto" if auto_transfer else r["source"],
            "needs_review": not auto_transfer and r["source"] == "llm" and r["confidence"] < CONFIDENCE_THRESHOLD,
        }
        if account_name:
            txn["account_name"] = account_name
            txn["account_type"] = account_type
        if auto_transfer:
            txn["auto_transfer"] = True
        transactions.append(txn)
        totals[category] = round(totals.get(category, 0.0) + t["amount"], 2)

    summary = [
        {"category": k, "total": v}
        for k, v in sorted(totals.items(), key=lambda x: x[1])
    ]

    transactions, recurring = enrich_with_recurring(transactions, date_type.today())
    upload_id = save_to_history(label, transactions, summary)
    _add_display_names(transactions)
    return {"upload_id": upload_id, "transactions": transactions, "summary": summary, "recurring": recurring}


class ReviewPayload(BaseModel):
    description: str
    category: str

@app.post("/review")
def save_review(payload: ReviewPayload, _: str = Depends(require_auth)):
    if payload.category not in ALLOWED:
        raise HTTPException(400, f"Category must be one of: {', '.join(sorted(ALLOWED))}")
    cache = load_cache(CACHE_PATH)
    key = normalize(payload.description)
    cache[key] = payload.category
    save_cache(CACHE_PATH, cache)
    return {"status": "saved", "key": key, "category": payload.category}


@app.get("/cache")
def get_cache(_: str = Depends(require_auth)):
    cache = load_cache(CACHE_PATH)
    entries = []
    for k, v in sorted(cache.items()):
        if isinstance(v, dict):
            entries.append({"key": k, "category": v.get("category", "Other"), "source": v.get("source", "")})
        else:
            entries.append({"key": k, "category": str(v), "source": ""})
    return {"entries": entries}


class CorrectPayload(BaseModel):
    description: str
    category: str

@app.post("/correct")
def save_correction(payload: CorrectPayload, _: str = Depends(require_auth)):
    if payload.category not in ALLOWED:
        raise HTTPException(400, f"Category must be one of: {', '.join(sorted(ALLOWED))}")
    cache = load_cache(CACHE_PATH)
    key = normalize(payload.description)
    cache[key] = {"category": payload.category, "source": "user_correction", "confidence": 1.0}
    save_cache(CACHE_PATH, cache)
    return {"status": "saved", "key": key, "category": payload.category}


@app.delete("/cache")
def delete_cache_entry(key: str, _: str = Depends(require_auth)):
    cache = load_cache(CACHE_PATH)
    if key not in cache:
        raise HTTPException(404, f"Key '{key}' not found in cache")
    del cache[key]
    save_cache(CACHE_PATH, cache)
    return {"status": "deleted", "key": key}


_MONTH_FROM_NAME: dict[str, int] = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

def _label_to_date(label: str) -> str | None:
    """Return a YYYY-MM-01 fallback date extracted from a statement label.

    Handles labels like 'UWCU Jan 2026', 'Chase Oct 2025', 'Amex (12th Dec 2025)'.
    Returns None if neither a month name nor a 4-digit year can be found.
    """
    year_m = re.search(r'\b(20\d{2})\b', label)
    if not year_m:
        return None
    year = year_m.group(1)
    for name, month in _MONTH_FROM_NAME.items():
        if re.search(r'\b' + name + r'\b', label, re.IGNORECASE):
            return f"{year}-{month:02d}-01"
    return None


def _apply_label_date_fallback(transactions: list, label: str) -> None:
    """For any transaction missing a date, inject a synthetic YYYY-MM-01 derived from the label."""
    fallback = _label_to_date(label)
    if not fallback:
        return
    for t in transactions:
        if not t.get("date"):
            t["date"] = fallback


def _upload_meta(transactions: list) -> dict:
    """Return max_txn_date (ISO str) and account_name for a list of transactions."""
    from recurring import _parse_date
    ref = date_type.today()
    dates = []
    account_name = ""
    for t in transactions:
        d = _parse_date(t.get("date"), ref)
        if d:
            dates.append(d)
        if not account_name and t.get("account_name"):
            account_name = t["account_name"]
    return {
        "max_txn_date": max(dates).isoformat() if dates else None,
        "account_name": account_name,
    }


@app.get("/history")
def list_history(_: str = Depends(require_auth)):
    HISTORY_DIR.mkdir(exist_ok=True)
    uploads = []
    for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        with open(path) as f:
            data = json.load(f)
        _apply_label_date_fallback(data["transactions"], data.get("label", ""))
        meta = _upload_meta(data["transactions"])
        uploads.append({
            "id": data["id"],
            "label": data["label"],
            "uploaded_at": data["uploaded_at"],
            "transaction_count": len(data["transactions"]),
            "summary": data["summary"],
            "max_txn_date": meta["max_txn_date"],
            "account_name": meta["account_name"],
        })
    return {"uploads": uploads}


@app.get("/history/{upload_id}")
def get_history_entry(upload_id: str, _: str = Depends(require_auth)):
    path = HISTORY_DIR / f"{upload_id}.json"
    if not path.exists():
        raise HTTPException(404, "Upload not found")
    with open(path) as f:
        data = json.load(f)
    ref = datetime.fromisoformat(data.get("uploaded_at", datetime.now().isoformat())).date()

    # Inject synthetic dates for transactions that have none (e.g. UWCU PDFs uploaded
    # before date extraction was added). Uses the statement label as the source.
    _apply_label_date_fallback(data["transactions"], data.get("label", ""))

    # Re-apply cache so user corrections survive reloads.
    # Skip auto-detected CC payments — those are never overridden by the cache.
    cache = load_cache(CACHE_PATH)
    for t in data["transactions"]:
        if t.get("auto_transfer"):
            continue
        key = normalize(t.get("description", ""))
        if key in cache:
            t["category"] = get_category_from_cache(cache[key])

    _, recurring = enrich_with_recurring(data["transactions"], ref)
    _add_display_names(data["transactions"])
    data["recurring"] = recurring
    return data


@app.delete("/history/{upload_id}")
def delete_history_entry(upload_id: str, _: str = Depends(require_auth)):
    path = HISTORY_DIR / f"{upload_id}.json"
    if not path.exists():
        raise HTTPException(404, "Upload not found")
    path.unlink()
    return {"status": "deleted", "id": upload_id}


class LabelPayload(BaseModel):
    label: str

@app.patch("/history/{upload_id}/label")
def rename_label(upload_id: str, payload: LabelPayload, _: str = Depends(require_auth)):
    label = payload.label.strip()
    if not label:
        raise HTTPException(400, "Label cannot be empty")
    if len(label) > 50:
        raise HTTPException(400, "Label must be 50 characters or fewer")
    path = HISTORY_DIR / f"{upload_id}.json"
    if not path.exists():
        raise HTTPException(404, "Upload not found")
    with open(path) as f:
        data = json.load(f)
    data["label"] = label
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"id": upload_id, "label": label}


class RecurringPayload(BaseModel):
    transactions: list

@app.post("/recurring")
def get_recurring(payload: RecurringPayload, _: str = Depends(require_auth)):
    txns, patterns = enrich_with_recurring(payload.transactions, date_type.today())
    return {"transactions": txns, "recurring": patterns}


@app.get("/zelle-aliases")
def get_zelle_aliases(_: str = Depends(require_auth)):
    return {"aliases": load_zelle_names()}

class ZelleAliasPayload(BaseModel):
    aliases: dict

@app.post("/zelle-aliases")
def save_zelle_aliases(payload: ZelleAliasPayload, _: str = Depends(require_auth)):
    names = load_zelle_names()
    names.update(payload.aliases)
    save_zelle_names(names)
    return {"status": "saved", "count": len(payload.aliases)}


@app.get("/accounts")
def get_accounts(_: str = Depends(require_auth)):
    return {"accounts": load_accounts()}

class AccountPayload(BaseModel):
    name: str
    type: str  # "bank" or "credit_card"

@app.post("/accounts")
def add_account(payload: AccountPayload, _: str = Depends(require_auth)):
    if payload.type not in ("bank", "credit_card"):
        raise HTTPException(400, "type must be 'bank' or 'credit_card'")
    accounts = load_accounts()
    if not any(a["name"].lower() == payload.name.lower() for a in accounts):
        accounts.append({"name": payload.name, "type": payload.type})
        save_accounts(accounts)
    return {"accounts": accounts}


class CyclePayload(BaseModel):
    name: str
    cycle_start_day: int | None = None  # None clears the field

@app.patch("/accounts/cycle")
def update_cycle(payload: CyclePayload, _: str = Depends(require_auth)):
    if payload.cycle_start_day is not None and not (1 <= payload.cycle_start_day <= 31):
        raise HTTPException(400, "cycle_start_day must be between 1 and 31")
    accounts = load_accounts()
    acct = next((a for a in accounts if a["name"].lower() == payload.name.lower()), None)
    if not acct:
        raise HTTPException(404, f"Account '{payload.name}' not found")
    if acct.get("type") != "credit_card":
        raise HTTPException(400, "Billing cycles only apply to credit card accounts")
    if payload.cycle_start_day is None:
        acct.pop("cycle_start_day", None)
    else:
        acct["cycle_start_day"] = payload.cycle_start_day
    save_accounts(accounts)
    return {"accounts": accounts}


@app.delete("/accounts")
def delete_account(name: str, _: str = Depends(require_auth)):
    accounts = load_accounts()
    new_accounts = [a for a in accounts if a["name"].lower() != name.lower()]
    if len(new_accounts) == len(accounts):
        raise HTTPException(404, f"Account '{name}' not found")
    save_accounts(new_accounts)
    return {"accounts": new_accounts}


@app.get("/orphaned-uploads")
def get_orphaned_uploads(_: str = Depends(require_auth)):
    """Return uploads that contain transactions with no account_name assigned."""
    HISTORY_DIR.mkdir(exist_ok=True)
    orphaned = []
    for path in sorted(HISTORY_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        count = sum(1 for t in data.get("transactions", []) if not t.get("account_name"))
        if count > 0:
            orphaned.append({
                "id": data["id"],
                "label": data.get("label", "Unlabeled"),
                "orphaned_count": count,
            })
    return {"uploads": orphaned}


class AccountAssignment(BaseModel):
    upload_id: str
    account_name: str
    account_type: str

class AssignAccountsPayload(BaseModel):
    assignments: list[AccountAssignment]

@app.post("/assign-accounts")
def assign_accounts(payload: AssignAccountsPayload, _: str = Depends(require_auth)):
    """Bulk-assign account_name + account_type to all unassigned transactions in each upload."""
    total = 0
    for a in payload.assignments:
        path = HISTORY_DIR / f"{a.upload_id}.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        for t in data.get("transactions", []):
            if not t.get("account_name"):
                t["account_name"] = a.account_name
                t["account_type"] = a.account_type
                total += 1
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    return {"assigned": total}


class PatchHistoryPayload(BaseModel):
    transactions: list

@app.patch("/history/{upload_id}")
def patch_history_entry(upload_id: str, payload: PatchHistoryPayload, _: str = Depends(require_auth)):
    path = HISTORY_DIR / f"{upload_id}.json"
    if not path.exists():
        raise HTTPException(404, "Upload not found")
    with open(path) as f:
        data = json.load(f)
    data["transactions"] = payload.transactions
    totals = {}
    for t in payload.transactions:
        cat = t["category"]
        totals[cat] = round(totals.get(cat, 0.0) + t["amount"], 2)
    data["summary"] = [
        {"category": k, "total": v}
        for k, v in sorted(totals.items(), key=lambda x: x[1])
    ]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return {"status": "updated"}


# ── Dashboard helpers ─────────────────────────────────────────────────────────

_MONTH_FULL = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December',
]

def _history_fingerprint() -> str:
    """MD5 of (name, mtime_ns, size) for every history file — changes on any add/modify."""
    files = sorted(HISTORY_DIR.glob("*.json"))
    parts = [(f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in files]
    return hashlib.md5(json.dumps(parts).encode()).hexdigest()

def _load_recurring_cache() -> dict | None:
    try:
        with open(RECURRING_CACHE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def _save_recurring_cache(fingerprint: str, patterns: list) -> None:
    with open(RECURRING_CACHE_PATH, "w") as f:
        json.dump({"computed_at": datetime.now(timezone.utc).isoformat(),
                   "fingerprint": fingerprint, "patterns": patterns}, f)

def _recurring_cache_valid(cached: dict, fingerprint: str) -> bool:
    if cached.get("fingerprint") != fingerprint:
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["computed_at"])).total_seconds()
        return age < RECURRING_CACHE_TTL
    except (KeyError, ValueError):
        return False

def _load_all_transactions() -> list[dict]:
    """Load every history transaction with label-date fallback and cache corrections applied."""
    HISTORY_DIR.mkdir(exist_ok=True)
    cat_cache = load_cache(CACHE_PATH)
    all_txns: list[dict] = []
    for path in HISTORY_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        txns = data["transactions"]
        _apply_label_date_fallback(txns, data.get("label", ""))
        for t in txns:
            if t.get("auto_transfer"):
                continue
            key = normalize(t.get("description", ""))
            if key in cat_cache:
                t["category"] = get_category_from_cache(cat_cache[key])
        all_txns.extend(txns)
    _add_display_names(all_txns)
    return all_txns


# ── Dashboard endpoint ────────────────────────────────────────────────────────

@app.get("/dashboard")
def get_dashboard(month: str = Query(default=None), _: str = Depends(require_auth)):
    from recurring import _parse_date

    today = date_type.today()

    # Parse optional ?month=YYYY-MM, default to current month
    if month:
        try:
            cur_y, cur_m = int(month[:4]), int(month[5:7])
        except (ValueError, IndexError):
            cur_y, cur_m = today.year, today.month
    else:
        cur_y, cur_m = today.year, today.month

    last_end  = date_type(cur_y, cur_m, 1) - timedelta(days=1)
    last_y, last_m = last_end.year, last_end.month

    EXCLUDED = {'Transfers', 'Credit Card Bill'}

    all_txns = _load_all_transactions()

    def get_dt(t):
        return _parse_date(t.get("date"), today)

    def in_month(t, y, m):
        d = get_dt(t)
        return d is not None and d.year == y and d.month == m

    cur_txns  = [t for t in all_txns if in_month(t, cur_y,  cur_m)]
    last_txns = [t for t in all_txns if in_month(t, last_y, last_m)]

    def month_stats(txns):
        filtered = [t for t in txns if t.get("category") not in EXCLUDED]
        spending = round(sum(t["amount"] for t in filtered if t["amount"] < 0), 2)
        income   = round(sum(t["amount"] for t in filtered if t["amount"] > 0), 2)
        return spending, income

    cur_sp,  cur_inc  = month_stats(cur_txns)
    last_sp, last_inc = month_stats(last_txns)
    cur_net  = round(cur_sp  + cur_inc,  2)
    last_net = round(last_sp + last_inc, 2)

    # Top 5 spending categories this month
    cat_totals: dict[str, float] = {}
    for t in cur_txns:
        cat = t.get("category", "Other")
        if cat in EXCLUDED or t["amount"] >= 0:
            continue
        cat_totals[cat] = round(cat_totals.get(cat, 0) + abs(t["amount"]), 2)
    total_spend = sum(cat_totals.values())
    top_categories = [
        {"category": cat, "amount": amt,
         "pct": round(amt / total_spend * 100, 1) if total_spend else 0}
        for cat, amt in sorted(cat_totals.items(), key=lambda x: -x[1])[:5]
    ]

    # Upcoming recurring — use file cache to avoid re-running detection on every load
    fingerprint = _history_fingerprint()
    cached      = _load_recurring_cache()
    if cached and _recurring_cache_valid(cached, fingerprint):
        patterns = cached["patterns"]
    else:
        patterns = detect_recurring(all_txns, today)
        _save_recurring_cache(fingerprint, patterns)

    upcoming: list[dict] = []
    for p in patterns:
        ne = p.get("next_expected")
        if not ne:
            continue
        try:
            ne_date = date_type.fromisoformat(ne)
        except ValueError:
            continue
        days = (ne_date - today).days
        if 0 <= days <= 30:
            upcoming.append({
                "display_name":   clean_description(p["display_name"]),
                "typical_amount": p["typical_amount"],
                "next_expected":  ne,
                "days_until":     days,
                "type":           p.get("type", ""),
            })
    upcoming.sort(key=lambda x: x["days_until"])

    # 8 most recent transactions across all accounts
    dated = [(t, get_dt(t)) for t in all_txns]
    dated = [(t, d) for t, d in dated if d is not None]
    dated.sort(key=lambda x: x[1], reverse=True)
    recent = [
        {
            "date":         t.get("date"),
            "display_name": t.get("display_name") or t.get("description"),
            "description":  t.get("description"),
            "amount":       t.get("amount"),
            "category":     t.get("category"),
            "account_name": t.get("account_name"),
        }
        for t, _ in dated[:8]
    ]

    return {
        "current_month": {
            "label":   f"{_MONTH_FULL[cur_m - 1]} {cur_y}",
            "spending": cur_sp,
            "income":   cur_inc,
            "net":      cur_net,
            "vs_last_month": {
                "label":          _MONTH_FULL[last_m - 1],
                "spending_delta": round(cur_sp  - last_sp,  2),
                "income_delta":   round(cur_inc - last_inc, 2),
                "net_delta":      round(cur_net - last_net, 2),
            },
        },
        "top_categories":      top_categories,
        "category_count":      len(cat_totals),
        "upcoming_recurring":  upcoming[:5],
        "recent_transactions": recent,
    }


@app.get("/dashboard/transactions")
def get_dashboard_transactions(
    month: str = Query(...),
    category: str = Query(default=None),
    kind: str = Query(default=None),
    _: str = Depends(require_auth),
):
    """Drill-down: transactions for a given month, optionally narrowed to a category or kind (spending/income)."""
    from recurring import _parse_date

    today = date_type.today()
    try:
        y, m = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format")

    EXCLUDED = {'Transfers', 'Credit Card Bill'}
    all_txns = _load_all_transactions()

    def get_dt(t):
        return _parse_date(t.get("date"), today)

    matches = []
    for t in all_txns:
        d = get_dt(t)
        if d is None or d.year != y or d.month != m:
            continue
        if t.get("category") in EXCLUDED:
            continue
        if category and t.get("category") != category:
            continue
        if kind == 'spending' and t["amount"] >= 0:
            continue
        if kind == 'income' and t["amount"] <= 0:
            continue
        matches.append((t, d))

    matches.sort(key=lambda x: x[1], reverse=True)

    return {
        "transactions": [
            {
                "date":         t.get("date"),
                "display_name": t.get("display_name") or t.get("description"),
                "description":  t.get("description"),
                "amount":       t.get("amount"),
                "category":     t.get("category"),
                "account_name": t.get("account_name"),
            }
            for t, _ in matches
        ],
    }
