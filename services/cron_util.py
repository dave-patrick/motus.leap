"""Stdlib-only 5-field cron evaluation for motus.leap scheduled jobs (P3).

Supports the subset required by the scheduler:

  * ``*``                       any value
  * ``a,b,c``                   lists
  * ``a-b``                     ranges (inclusive)
  * ``*/n``  and  ``a-b/n``     steps

Fields are: minute hour day-of-month month day-of-week. Day-of-week accepts
0-6 (0 = Sunday) and 7 (also Sunday, normalized to 0); month/day-of-week also
accept common 3-letter names (jan..dec, sun..sat).

NOTE: day-of-month and day-of-week are combined with AND semantics (both must
match). This is the conservative, predictable choice for the simple schedules
the Jobs UI generates; it avoids the subtle "either matches" cron rule.

Never executes any user text — ``parse_cron`` only ever produces integer sets.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# 3-letter names for day-of-week / month (cron uses 0=Sun..6=Sat).
_DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3,
    "thu": 4, "fri": 5, "sat": 6,
}
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _coerce(value: str, names) -> int:
    """Coerce a single cron token to int (or named value)."""
    value = value.strip().lower()
    try:
        return int(value)
    except ValueError:
        if names and value in names:
            return names[value]
        raise ValueError(f"invalid cron value '{value}'")


def _expand_field(field: str, lo: int, hi: int, names=None) -> Set[int]:
    """Expand one cron field into the set of integers it matches."""
    field = field.strip()
    if not field:
        raise ValueError("empty cron field")

    result: Set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"empty list item in '{field}'")

        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError(f"bad step '{step_s}'")
            part = base.strip()
        else:
            step = 1

        if part == "*":
            vals = list(range(lo, hi + 1))
        elif "-" in part:
            a, b = part.split("-", 1)
            a_v = _coerce(a, names)
            b_v = _coerce(b, names)
            if a_v > b_v:
                raise ValueError(f"range start > end: {part}")
            vals = list(range(a_v, b_v + 1))
        else:
            vals = [_coerce(part, names)]

        for v in vals:
            if v < lo or v > hi:
                # dow 7 is valid and normalized to 0 below.
                if not (hi == 7 and v == 7):
                    raise ValueError(f"value {v} out of range [{lo},{hi}]")
            result.add(v)

    if step != 1:
        result = {v for v in result if (v - lo) % step == 0}
    return result


def parse_cron(expr: str) -> Tuple[Set[int], ...]:
    """Parse a 5-field cron expression into (minute, hour, day, month, dow) sets.

    Raises ValueError on any malformed input.
    """
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"cron must have 5 fields, got {len(parts)}")
    minute = _expand_field(parts[0], 0, 59)
    hour = _expand_field(parts[1], 0, 23)
    day = _expand_field(parts[2], 1, 31)
    month = _expand_field(parts[3], 1, 12, _MONTH_NAMES)
    dow = _expand_field(parts[4], 0, 7, _DOW_NAMES)
    dow = {(0 if v == 7 else v) for v in dow}  # normalize 7 -> 0 (Sunday)
    return (minute, hour, day, month, dow)


def cron_valid(expr: str) -> bool:
    """Return True iff ``expr`` is a parseable 5-field cron expression."""
    try:
        parse_cron(expr)
        return True
    except Exception:
        return False


def matches(expr_or_sets, dt: datetime) -> bool:
    """Return True if ``dt`` satisfies the cron expression.

    ``expr_or_sets`` may be a cron string or a tuple of sets from parse_cron.
    """
    sets = parse_cron(expr_or_sets) if isinstance(expr_or_sets, str) else expr_or_sets
    minute, hour, day, month, dow = sets
    if dt.minute not in minute:
        return False
    if dt.hour not in hour:
        return False
    if dt.day not in day:
        return False
    if dt.month not in month:
        return False
    # Python weekday(): Mon=0..Sun=6. Cron dow: 0=Sun..6=Sat.
    py_dow = (dt.weekday() + 1) % 7  # Mon=1..Sun=0
    if py_dow not in dow:
        return False
    return True


def next_run(expr_or_sets, after: Optional[datetime] = None) -> Optional[datetime]:
    """Return the next datetime (naive, local) strictly after ``after`` that
    satisfies the cron expression, or None if none within ~4 years.

    Iterates minute-by-minute (bounded) — cheap for the sparse schedules this
    feature generates, and dependency-free.
    """
    sets = parse_cron(expr_or_sets) if isinstance(expr_or_sets, str) else expr_or_sets
    if after is None:
        after = datetime.now()
    cur = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    horizon = after + timedelta(days=4 * 366)
    while cur <= horizon:
        if matches(sets, cur):
            return cur
        cur += timedelta(minutes=1)
    return None
