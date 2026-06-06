"""
Billing cycle utilities.

get_statement_period(year, month, cycle_start_day) is the only public entry point.
"""
import calendar
from datetime import date


def get_statement_period(year: int, month: int, cycle_start_day: int) -> tuple[date, date]:
    """
    Return (start_date, end_date) for the statement period labeled as month/year.

    cycle_start_day=1  → full calendar month  (May 1 – May 31)
    cycle_start_day=13 → prior-month anchor    (Apr 13 – May 12)

    Edge cases handled:
    - January with cycle_start_day > 1 → start falls in December of the prior year
    - cycle_start_day exceeds last day of previous month (e.g. day 31 in Feb) → clamped
    """
    if cycle_start_day == 1:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    # Previous month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    last_day_prev = calendar.monthrange(prev_year, prev_month)[1]
    start_day = min(cycle_start_day, last_day_prev)
    start = date(prev_year, prev_month, start_day)
    end   = date(year, month, cycle_start_day - 1)
    return start, end
