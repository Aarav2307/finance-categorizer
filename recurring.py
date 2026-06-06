"""
Recurring transaction detection.

detect_recurring(transactions, reference_date) is the only public entry point.
Each transaction dict needs: description (str), amount (float), date (str MM/DD or MM/DD/YYYY).
"""

import re
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional


# ── Merchant normalisation ────────────────────────────────────────────────────

# Named payment-processor prefixes to strip entirely (with optional trailing *)
_PROCESSOR_PREFIX_RE = re.compile(
    r'^(?:APLPAY|APPLEPAYPAY|PAYPAL|SQ|PP|TST|ACH|POS|ONLINE|DEBIT|CHECKCARD)\s*\*?\s*',
)

# Any remaining asterisk in the description is a separator — replace with space.
# "OPENAI *CHATGPT" → "OPENAI CHATGPT"  (processor prefix NOT stripped for OPENAI)
_ASTERISK_RE = re.compile(r'\s*\*\s*')

# Slash + everything after (to end of string): normalises APPLE.COM/BILL and APPLE.COM/BILINTERNET CHARGE → APPLE.COM
_SLASH_SUFFIX_RE = re.compile(r'/.*$')

_STORE_NUM_RE    = re.compile(r'\s*#\d+')
_TRAILING_NUM_RE = re.compile(r'\s+\d{6,}\s*$')
_CORP_SUFFIX_RE  = re.compile(r'\s+(INC|LLC|LTD|CORP|CO)\.?\s*$', re.I)
_WHITESPACE_RE   = re.compile(r'\s+')


def normalize_merchant(desc: str) -> str:
    s = desc.strip().upper()
    # 1. Strip payment-processor prefixes (SQ *, PP*, AplPay, etc.)
    s = _PROCESSOR_PREFIX_RE.sub('', s)
    # 2. Replace remaining asterisks with a space (OPENAI *CHATGPT → OPENAI CHATGPT)
    s = _ASTERISK_RE.sub(' ', s)
    # 3. Strip slash and everything after (collapses APPLE.COM/BILL variants)
    s = _SLASH_SUFFIX_RE.sub('', s)
    # 4. Strip store numbers, trailing transaction IDs, corporate suffixes
    s = _STORE_NUM_RE.sub('', s)
    s = _TRAILING_NUM_RE.sub('', s)
    s = _CORP_SUFFIX_RE.sub('', s)
    # 5. Collapse whitespace
    s = _WHITESPACE_RE.sub(' ', s).strip()
    return s


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_date(date_str: Optional[str], ref: date) -> Optional[date]:
    if not date_str:
        return None
    s = date_str.strip()

    # MM/DD/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    # MM/DD/YY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', s)
    if m:
        try:
            return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    # MM/DD — infer year from ref date
    m = re.match(r'^(\d{1,2})/(\d{1,2})$', s)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = ref.year
        # Statement month is December but ref is January → previous year
        if ref.month <= 2 and month >= 11:
            year -= 1
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


# ── Amount-tier splitting ─────────────────────────────────────────────────────

def _split_amount_tiers(entries: list[dict], threshold: float = 0.25) -> list[list[dict]]:
    """
    Split entries into amount clusters. Entries are sorted by absolute amount;
    a new cluster starts when the next entry differs from the current cluster's
    median by more than `threshold` (25%). Returns a list of entry-groups.
    """
    if not entries:
        return []
    sorted_entries = sorted(entries, key=lambda e: abs(e['amount']))
    tiers: list[list[dict]] = []
    current: list[dict] = [sorted_entries[0]]

    for entry in sorted_entries[1:]:
        cluster_median = statistics.median(abs(e['amount']) for e in current)
        if cluster_median == 0:
            current.append(entry)
            continue
        ratio = abs(abs(entry['amount']) - cluster_median) / cluster_median
        if ratio <= threshold:
            current.append(entry)
        else:
            tiers.append(current)
            current = [entry]
    tiers.append(current)
    return tiers


# ── Category exclusions ───────────────────────────────────────────────────────

# Transactions in these categories are discretionary or flow-through — never
# recurring committed costs regardless of how frequently they appear.
_EXCLUDED_CATEGORIES: frozenset[str] = frozenset({
    'Dining', 'Groceries', 'Shopping',
    'Zelle', 'Transfers', 'Income', 'Credit Card Bill',
})


# ── Non-recurring blocklist ───────────────────────────────────────────────────

# Merchants that purchase frequently but are NOT subscriptions or predictable
# fixed costs. Excluded from every detection tier (regular and frequent).
# Each entry is matched against the start of the normalised merchant_key.
_NON_RECURRING_PREFIXES: frozenset[str] = frozenset({
    'AMZN',
    'AMAZON',
    'RAISING CANE',
    'UBER',
    'LYFT',
})

# Keys that match a blocked prefix but are legitimate subscriptions
_RECURRING_EXCEPTIONS: frozenset[str] = frozenset({
    'AMAZON PRIME',
    'AMZN PRIME',
})

def _is_blocked(merchant_key: str) -> bool:
    k = merchant_key.upper()
    if k in _RECURRING_EXCEPTIONS:
        return False
    return any(k.startswith(p) for p in _NON_RECURRING_PREFIXES)


# ── Frequency & tier classification ──────────────────────────────────────────

# Widened windows to handle real-world payment-day variation:
#   monthly: 20–40 (was 25–35) — covers months with billing-day shifts
#   weekly:   5–9  (was 6–8)   — covers Mon→Sat variation
#   annual: 350–380 (was 355–375) — covers leap years and day-of-year drift
_FREQ_RANGES = {
    'weekly':  (5,   9),
    'monthly': (20, 40),
    'annual':  (350, 380),
}

# Minimum occurrences to qualify for the "frequent" (irregular) tier
_FREQUENT_MIN = 5


def _classify_frequency(intervals: list[int]) -> Optional[str]:
    """
    Classify intervals using their mean rather than checking each pair
    individually. This handles cases where billing days shift month-to-month:
    e.g. intervals [33, 29] → mean 31 → monthly.
    """
    if not intervals:
        return None
    avg = sum(intervals) / len(intervals)
    for freq, (lo, hi) in _FREQ_RANGES.items():
        if lo <= avg <= hi:
            return freq
    return None


def _classify_tier(amounts: list[float]) -> str:
    abs_amounts = [abs(a) for a in amounts]
    med = statistics.median(abs_amounts)
    if med == 0:
        return 'variable_bill'
    max_diff = max(abs(a - med) for a in abs_amounts)
    if max_diff <= 0.01:
        return 'subscription'
    if max_diff / med <= 0.10:
        return 'fixed_bill'
    return 'variable_bill'


# ── Public API ────────────────────────────────────────────────────────────────

def detect_recurring(
    transactions: list[dict],
    reference_date: Optional[date] = None,
) -> list[dict]:
    """
    Return a list of recurring-pattern dicts detected across the given transactions.
    Transactions that lack a parseable date are skipped.

    Two detection tiers:
      1. Regular: weekly / monthly / annual — requires ≥2 occurrences with a
         consistent average interval.
      2. Frequent: ≥5 occurrences with no consistent interval. These are
         irregular high-frequency purchases (vending, coffee, parking) and are
         NOT included in fixed monthly spend totals.
    """
    if reference_date is None:
        reference_date = date.today()

    groups: dict[str, list[dict]] = defaultdict(list)
    for t in transactions:
        if t.get('category') in _EXCLUDED_CATEGORIES:
            continue
        key = normalize_merchant(t.get('description', ''))
        if not key:
            continue
        d = _parse_date(t.get('date'), reference_date)
        if d is None:
            continue
        groups[key].append({
            'description': t.get('description', ''),
            'amount':      float(t.get('amount', 0)),
            'date':        d,
        })

    patterns = []
    classified: set[str] = set()

    # ── Pass 1: regular interval detection (weekly / monthly / annual) ────────
    for merchant_key, entries in groups.items():
        if _is_blocked(merchant_key):
            continue
        # Split entries into amount tiers before interval analysis so that a
        # merchant with two distinct price points (e.g. APPLE.COM $2.99 and
        # $39.70) produces separate recurring patterns instead of one with a
        # meaningless blended median.
        tiers = _split_amount_tiers(entries)
        qualified: list[dict] = []

        for tier_entries in tiers:
            if len(tier_entries) < 2:
                continue

            tier_entries_sorted = sorted(tier_entries, key=lambda e: e['date'])
            dates   = [e['date']   for e in tier_entries_sorted]
            amounts = [e['amount'] for e in tier_entries_sorted]

            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            freq = _classify_frequency(intervals)
            if freq is None:
                continue

            tier_type      = _classify_tier(amounts)
            typical_amount = round(statistics.median(amounts), 2)
            last_seen      = max(dates)
            median_gap     = int(statistics.median(intervals))
            next_expected  = last_seen + timedelta(days=median_gap)
            # If the projected date is already past (e.g. a subscription whose
            # description changed and newer charges weren't grouped here), keep
            # advancing by the same gap until we land on a future date.
            while next_expected < reference_date:
                next_expected += timedelta(days=median_gap)

            desc_counts: dict[str, int] = defaultdict(int)
            for e in tier_entries_sorted:
                desc_counts[e['description']] += 1
            display_name = max(desc_counts, key=desc_counts.__getitem__)

            qualified.append({
                'merchant_key':   merchant_key,
                'display_name':   display_name,
                'type':           tier_type,
                'frequency':      freq,
                'typical_amount': typical_amount,
                'occurrences':    len(tier_entries_sorted),
                'last_seen':      last_seen.isoformat(),
                'next_expected':  next_expected.isoformat(),
            })

        if not qualified:
            continue

        classified.add(merchant_key)

        # When multiple tiers both qualify, disambiguate display names with amounts
        if len(qualified) > 1:
            for p in qualified:
                p['display_name'] = f"{p['display_name']} (${abs(p['typical_amount']):.2f})"

        patterns.extend(qualified)

    # ── Pass 2: frequent tier (5+ occurrences, no consistent interval) ────────
    for merchant_key, entries in groups.items():
        if _is_blocked(merchant_key):
            continue
        if merchant_key in classified:
            continue
        if len(entries) < _FREQUENT_MIN:
            continue

        entries.sort(key=lambda e: e['date'])
        amounts = [e['amount'] for e in entries]
        typical_amount = round(statistics.median(amounts), 2)

        desc_counts: dict[str, int] = defaultdict(int)
        for e in entries:
            desc_counts[e['description']] += 1
        display_name = max(desc_counts, key=desc_counts.__getitem__)

        patterns.append({
            'merchant_key':   merchant_key,
            'display_name':   display_name,
            'type':           'frequent',
            'frequency':      'frequent',
            'typical_amount': typical_amount,
            'occurrences':    len(entries),
            'last_seen':      max(e['date'] for e in entries).isoformat(),
            'next_expected':  None,
        })

    # Regular patterns first (most expensive first), then frequent (most common first)
    regular  = sorted([p for p in patterns if p['frequency'] != 'frequent'], key=lambda p: p['typical_amount'])
    frequent = sorted([p for p in patterns if p['frequency'] == 'frequent'], key=lambda p: -p['occurrences'])
    return regular + frequent
