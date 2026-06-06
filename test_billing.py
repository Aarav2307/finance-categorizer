"""
Unit tests for get_statement_period().
Run with: python test_billing.py
"""
from datetime import date
from billing import get_statement_period


def test(label, year, month, day, expected_start, expected_end):
    start, end = get_statement_period(year, month, day)
    ok = start == expected_start and end == expected_end
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")
    if not ok:
        print(f"         expected {expected_start} – {expected_end}")
        print(f"         got      {start} – {end}")
    return ok


print("=== get_statement_period tests ===\n")
results = [
    test("May 2026, day 13  → Apr 13 – May 12",
         2026, 5, 13, date(2026, 4, 13), date(2026, 5, 12)),

    test("May 2026, day 1   → May 1 – May 31 (calendar month)",
         2026, 5, 1,  date(2026, 5,  1), date(2026, 5, 31)),

    test("Jan 2026, day 15  → Dec 15 2025 – Jan 14 2026",
         2026, 1, 15, date(2025, 12, 15), date(2026, 1, 14)),

    test("Mar 2026, day 31  → Feb 28 2026 – Mar 30 2026 (clamped, non-leap)",
         2026, 3, 31, date(2026, 2, 28), date(2026, 3, 30)),

    test("Mar 2024, day 31  → Feb 29 2024 – Mar 30 2024 (clamped, leap year)",
         2024, 3, 31, date(2024, 2, 29), date(2024, 3, 30)),

    test("Dec 2026, day 22  → Nov 22 – Dec 21",
         2026, 12, 22, date(2026, 11, 22), date(2026, 12, 21)),

    test("Feb 2026, day 28  → Jan 28 – Feb 27",
         2026, 2, 28, date(2026, 1, 28), date(2026, 2, 27)),

    test("Jan 2026, day 1   → Jan 1 – Jan 31 (calendar month)",
         2026, 1, 1,  date(2026, 1,  1), date(2026, 1, 31)),
]
print()
passed = sum(results)
print(f"{passed}/{len(results)} tests passed")
if passed < len(results):
    raise SystemExit(1)
