"""
Pure business rules for the mock CVS Health HR systems of record.

No I/O here: every function takes plain values and returns typed
dataclasses or primitives, so the four MCP adapters (``cvs_identity``,
``workday_hcm``, ``time_attendance``, ``servicenow_hrsd``) and the admin REST
API share one tested source of truth. "Rules compute, the model explains":
every number, date and display string the voice agent speaks comes from
here.

Pay calendar (relative to an as-of date, today by default; the
``CVS_HR_AS_OF`` env var overrides it):
    * Work weeks run Sunday-Saturday. The last closed period ends on the
      most recent Saturday on or before the as-of date (a Saturday as-of
      date counts as closed that day).
    * The meal deductions in the seed fall on that week's Mon, Wed and Thu.
    * Payday = period end + 13 days (a Friday); later paydays every 14 days.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

AS_OF_ENV = "CVS_HR_AS_OF"
SATURDAY = 5  # date.weekday()
PAYDAY_OFFSET_DAYS = 13
PAY_CYCLE_DAYS = 14
OVERTIME_THRESHOLD_HOURS = 40.0
OT_MULTIPLIER = Decimal("1.5")
OFF_CYCLE_THRESHOLD_HOURS = 4
OFF_CYCLE_BUSINESS_DAYS = 3
PAY_CORRECTION_RULE_ID = "PAY-CORRECTIONS v2.4"
HOURS_PER_PTO_DAY = 8.0

_EN_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_ES_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
_ES_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
              "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ---------------------------------------------------------------------------
# As-of date and pay calendar
# ---------------------------------------------------------------------------

def as_of_date(today: Optional[date] = None, env: Optional[dict] = None) -> date:
    """
    Resolve the as-of date: ``CVS_HR_AS_OF`` (ISO ``YYYY-MM-DD``) if set and
    valid, otherwise ``today`` (defaults to ``date.today()``).

    An invalid override is logged and ignored rather than raised, because
    these servers share one process with unrelated demos.
    """
    env = os.environ if env is None else env
    raw = (env.get(AS_OF_ENV) or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            logger.warning("Ignoring invalid %s=%r; using today", AS_OF_ENV, raw)
    return today or date.today()


def last_closed_period_end(as_of: date) -> date:
    """Most recent Saturday on or before ``as_of`` (``as_of`` itself if a Saturday)."""
    return as_of - timedelta(days=(as_of.weekday() - SATURDAY) % 7)


def week_dates(period_end: date) -> list[date]:
    """The seven dates (Sunday..Saturday) of the week ending ``period_end``."""
    return [period_end - timedelta(days=6 - i) for i in range(7)]


@dataclass(frozen=True)
class PayCalendar:
    """Pay calendar for the last closed period as of a date."""

    as_of: date
    period_start: date
    period_end: date
    prior_period_end: date
    first_pay_date: date

    def pay_date(self, n: int) -> date:
        """The ``n``-th payday (1-based) from the closed period's payday."""
        if n < 1:
            raise ValueError("n must be >= 1")
        return self.first_pay_date + timedelta(days=PAY_CYCLE_DAYS * (n - 1))

    @property
    def deduction_dates(self) -> list[date]:
        """Mon, Wed and Thu of the closed week (where the seed's deductions fall)."""
        return [self.period_start + timedelta(days=d) for d in (1, 3, 4)]


def pay_calendar(as_of: date) -> PayCalendar:
    """Build the :class:`PayCalendar` for ``as_of``."""
    end = last_closed_period_end(as_of)
    return PayCalendar(
        as_of=as_of,
        period_start=end - timedelta(days=6),
        period_end=end,
        prior_period_end=end - timedelta(days=7),
        first_pay_date=end + timedelta(days=PAYDAY_OFFSET_DAYS),
    )


def add_business_days(start: date, days: int) -> date:
    """``start`` plus ``days`` Mon-Fri business days."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


# ---------------------------------------------------------------------------
# Display strings (English + Spanish)
# ---------------------------------------------------------------------------

def ordinal_en(n: int) -> str:
    """``1 -> '1st'``, ``12 -> '12th'``, ``23 -> '23rd'``."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def date_display_en(d: date) -> str:
    """``'Friday, October 16th'``."""
    return f"{_EN_WEEKDAYS[d.weekday()]}, {_EN_MONTHS[d.month - 1]} {ordinal_en(d.day)}"


def date_display_es(d: date) -> str:
    """``'viernes 16 de octubre'``."""
    return f"{_ES_WEEKDAYS[d.weekday()]} {d.day} de {_ES_MONTHS[d.month - 1]}"


def _join_en(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _join_es(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def days_display_en(days: Iterable[date]) -> str:
    """
    Spoken list of days: ``'Monday the 28th, Wednesday the 30th and
    Thursday, October 1st'``. The month is named only when it changes from
    the previous day in the list.
    """
    parts, prev = [], None
    for d in sorted(days):
        wd = _EN_WEEKDAYS[d.weekday()]
        if prev is not None and d.month != prev.month:
            parts.append(f"{wd}, {_EN_MONTHS[d.month - 1]} {ordinal_en(d.day)}")
        else:
            parts.append(f"{wd} the {ordinal_en(d.day)}")
        prev = d
    return _join_en(parts)


def days_display_es(days: Iterable[date]) -> str:
    """
    Spoken list of days in Spanish: ``'lunes 28, miércoles 30 de septiembre
    y jueves 1 de octubre'``. The month follows the last day of each month.
    """
    ordered = sorted(days)
    parts = []
    for i, d in enumerate(ordered):
        text = f"{_ES_WEEKDAYS[d.weekday()]} {d.day}"
        last_of_month = i == len(ordered) - 1 or ordered[i + 1].month != d.month
        if last_of_month:
            text += f" de {_ES_MONTHS[d.month - 1]}"
        parts.append(text)
    return _join_es(parts)


def money(value) -> Decimal:
    """Round to cents, half-up (``41.625 -> 41.63``)."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def amount_display_en(value) -> str:
    """``'$41.63'``."""
    return f"${money(value):,.2f}"


def amount_display_es(value) -> str:
    """``'41 dólares con 63 centavos'`` (``'1 dólar'``, no cents part when zero)."""
    cents_total = int(money(value) * 100)
    dollars, cents = divmod(cents_total, 100)
    text = f"{dollars} {'dólar' if dollars == 1 else 'dólares'}"
    if cents:
        text += f" con {cents} {'centavo' if cents == 1 else 'centavos'}"
    return text


def month_part_label(d: date) -> str:
    """``'early'`` (days 1-7), ``'mid'`` (8-21) or ``'late'`` (22+)."""
    if d.day <= 7:
        return "early"
    if d.day <= 21:
        return "mid"
    return "late"


def target_label_en(d: date) -> str:
    """``'mid-November'``, ``'early October'``, ``'late May'``."""
    part = month_part_label(d)
    month = _EN_MONTHS[d.month - 1]
    return f"mid-{month}" if part == "mid" else f"{part} {month}"


def target_label_es(d: date) -> str:
    """``'mediados de noviembre'``, ``'principios de octubre'``, ``'finales de mayo'``."""
    prefix = {"early": "principios", "mid": "mediados", "late": "finales"}[month_part_label(d)]
    return f"{prefix} de {_ES_MONTHS[d.month - 1]}"


# ---------------------------------------------------------------------------
# Timecards and overtime pricing
# ---------------------------------------------------------------------------

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def segment_hours(segments: Iterable[tuple[str, str]]) -> float:
    """Total worked hours across ``(in, out)`` ``HH:MM`` punch pairs."""
    return sum(_minutes(out) - _minutes(in_) for in_, out in segments) / 60.0


@dataclass(frozen=True)
class TimecardDay:
    """One worked day: punches, any auto meal deduction, and whether a break was punched."""

    work_date: date
    segments: tuple[tuple[str, str], ...]
    auto_deduct_minutes: int = 0
    break_punched: bool = True

    @property
    def hours_worked(self) -> float:
        return segment_hours(self.segments)

    @property
    def is_discrepancy(self) -> bool:
        """An auto meal deduction was taken but the punches show no break."""
        return self.auto_deduct_minutes > 0 and not self.break_punched


@dataclass(frozen=True)
class OvertimePrice:
    """Price of restoring ``hours`` of deducted time in a week."""

    hours: float
    ot_hours: float
    regular_hours: float
    overtime: bool
    base_rate_usd: Decimal
    ot_rate_usd: Decimal
    amount_usd: Decimal


def ot_rate(base_rate) -> Decimal:
    """Time-and-a-half rate, rounded to cents (``18.50 -> 27.75``)."""
    return money(Decimal(str(base_rate)) * OT_MULTIPLIER)


def price_restored_hours(hours: float, week_hours_worked: float, base_rate) -> OvertimePrice:
    """
    Price restoring ``hours`` of wrongly deducted time.

    The restored hours are overtime up to the number of hours actually
    worked above 40 that week; anything beyond that is paid at base rate.
    Daniel: 1.5 h, 43.0 h worked, base 18.50 -> 1.5 h OT at 27.75 = $41.63.
    """
    hours_d = Decimal(str(hours))
    base = money(base_rate)
    ot = ot_rate(base)
    ot_capacity = max(Decimal("0"), Decimal(str(week_hours_worked)) - Decimal(str(OVERTIME_THRESHOLD_HOURS)))
    ot_hours = min(hours_d, ot_capacity)
    regular = hours_d - ot_hours
    amount = money(ot_hours * ot + regular * base)
    return OvertimePrice(
        hours=float(hours_d), ot_hours=float(ot_hours), regular_hours=float(regular),
        overtime=ot_hours > 0, base_rate_usd=base, ot_rate_usd=ot, amount_usd=amount,
    )


def hours_short(days: Iterable[TimecardDay], dates: Optional[Iterable[date]] = None) -> float:
    """Hours wrongly deducted on discrepancy days (optionally only ``dates``)."""
    wanted = None if dates is None else set(dates)
    minutes = sum(
        d.auto_deduct_minutes for d in days
        if d.is_discrepancy and (wanted is None or d.work_date in wanted)
    )
    return minutes / 60.0


# ---------------------------------------------------------------------------
# Payroll correction rule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PayCorrectionDecision:
    """Where a pay correction lands (read-only: nothing writes to payroll)."""

    hours: float
    off_cycle: bool
    off_cycle_threshold_hours: float
    rule_id: str
    pay_date: date


def evaluate_pay_correction(hours: float, cal: PayCalendar) -> PayCorrectionDecision:
    """
    Apply PAY-CORRECTIONS v2.4: a correction under 4 hours goes on the next
    regular paycheck; 4 hours or more is paid off-cycle within 3 business
    days of the as-of date.
    """
    off_cycle = hours >= OFF_CYCLE_THRESHOLD_HOURS
    pay_date = add_business_days(cal.as_of, OFF_CYCLE_BUSINESS_DAYS) if off_cycle else cal.first_pay_date
    return PayCorrectionDecision(
        hours=hours, off_cycle=off_cycle, off_cycle_threshold_hours=OFF_CYCLE_THRESHOLD_HOURS,
        rule_id=PAY_CORRECTION_RULE_ID, pay_date=pay_date,
    )


# ---------------------------------------------------------------------------
# PTO
# ---------------------------------------------------------------------------

def hours_to_days(hours: float) -> float:
    """PTO hours as 8-hour days, one decimal (``62.5 -> 7.8``)."""
    return float(Decimal(str(hours / HOURS_PER_PTO_DAY)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class PtoProjection:
    """When a PTO balance reaches a target."""

    balance_hours: float
    target_hours: float
    accrual_per_period_hours: float
    hours_needed: float
    periods_needed: int
    already_enough: bool
    target_pay_date: Optional[date]


def project_time_off(balance_hours: float, accrual_per_period_hours: float,
                     target_hours: float, cal: PayCalendar) -> PtoProjection:
    """
    Project when ``balance_hours`` reaches ``target_hours`` at one accrual per
    pay period, landing on that period's payday (the 1st payday is the
    closed period's). 62.5 h -> 80 h at 6.15 h: 17.5 h, 3 periods, 3rd payday.
    """
    if accrual_per_period_hours <= 0:
        raise ValueError("accrual_per_period_hours must be positive")
    needed = float(Decimal(str(target_hours)) - Decimal(str(balance_hours)))
    if needed <= 0:
        return PtoProjection(balance_hours, target_hours, accrual_per_period_hours,
                             0.0, 0, True, None)
    periods = math.ceil(round(needed / accrual_per_period_hours, 9))
    return PtoProjection(balance_hours, target_hours, accrual_per_period_hours,
                         needed, periods, False, cal.pay_date(periods))


# ---------------------------------------------------------------------------
# Identity input handling
# ---------------------------------------------------------------------------

def digits_only(value) -> str:
    """Strip everything but digits (``'774-2318' -> '7742318'``)."""
    return re.sub(r"\D", "", str(value or ""))


def classify_identifier(colleague_id: str, mobile: str) -> tuple[str, str]:
    """
    Decide what the caller gave. Returns ``(kind, digits)`` where kind is
    ``'colleague_id'`` (7 digits), ``'mobile'`` (10 digits, or 11 with a
    leading 1) or ``'invalid'``. A value in the "wrong" field is classified
    by its length, so a mobile said as an ID still works.
    """
    for raw in (colleague_id, mobile):
        d = digits_only(raw)
        if len(d) == 11 and d.startswith("1"):
            d = d[1:]
        if len(d) == 7:
            return "colleague_id", d
        if len(d) == 10:
            return "mobile", d
    given = digits_only(colleague_id) or digits_only(mobile)
    return "invalid", given


def mask_digits(value: str, keep: int = 2) -> str:
    """Mask all but the last ``keep`` digits (``'7742318' -> '*****18'``)."""
    d = digits_only(value)
    if not d:
        return ""
    return "*" * max(0, len(d) - keep) + d[-keep:]


_DIGIT_RUN = re.compile(r"\d[\d\-\s().]{2,}\d")


def mask_digit_runs(text: str, keep: int = 2) -> str:
    """Mask every run of 4+ digits (with separators) in free text, keeping the last ``keep``."""
    def repl(m: re.Match) -> str:
        d = digits_only(m.group(0))
        return mask_digits(d, keep) if len(d) >= 4 else m.group(0)
    return _DIGIT_RUN.sub(repl, text or "")
