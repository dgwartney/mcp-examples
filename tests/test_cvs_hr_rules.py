"""
Unit tests for mcp_server_kit.cvs_hr_rules (pure business rules, no I/O).

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from datetime import date
from decimal import Decimal

import pytest

from mcp_server_kit import cvs_hr_rules as rules


class TestAsOfDate:

    def test_default_is_today(self):
        assert rules.as_of_date(today=date(2026, 1, 2), env={}) == date(2026, 1, 2)

    def test_env_override(self):
        assert rules.as_of_date(env={"CVS_HR_AS_OF": "2026-10-08"}) == date(2026, 10, 8)

    def test_invalid_override_falls_back_to_today(self, caplog):
        got = rules.as_of_date(today=date(2026, 1, 2), env={"CVS_HR_AS_OF": "tomorrow"})
        assert got == date(2026, 1, 2)
        assert "Ignoring invalid" in caplog.text

    def test_reads_os_environ_by_default(self, monkeypatch):
        monkeypatch.setenv("CVS_HR_AS_OF", "2026-09-01")
        assert rules.as_of_date() == date(2026, 9, 1)

    def test_os_environ_unset_uses_real_today(self, monkeypatch):
        monkeypatch.delenv("CVS_HR_AS_OF", raising=False)
        assert rules.as_of_date() == date.today()


class TestLastClosedPeriodEnd:

    @pytest.mark.parametrize("as_of, expected", [
        (date(2026, 10, 8), date(2026, 10, 3)),   # Thu (demo day)
        (date(2026, 10, 7), date(2026, 10, 3)),   # Wed (rehearsal day)
        (date(2026, 10, 3), date(2026, 10, 3)),   # Saturday itself counts as closed
        (date(2026, 10, 4), date(2026, 10, 3)),   # Sunday after
        (date(2026, 10, 9), date(2026, 10, 3)),   # Friday before the next Saturday
        (date(2026, 10, 10), date(2026, 10, 10)),  # next Saturday
        (date(2026, 9, 1), date(2026, 8, 29)),    # Tue (the recording)
    ])
    def test_most_recent_saturday_on_or_before(self, as_of, expected):
        got = rules.last_closed_period_end(as_of)
        assert got == expected
        assert got.weekday() == rules.SATURDAY

    def test_week_dates_run_sunday_to_saturday(self):
        days = rules.week_dates(date(2026, 10, 3))
        assert days[0] == date(2026, 9, 27) and days[0].weekday() == 6
        assert days[-1] == date(2026, 10, 3)


class TestPayCalendar:

    def test_demo_calendar(self):
        cal = rules.pay_calendar(date(2026, 10, 8))
        assert cal.period_start == date(2026, 9, 27)
        assert cal.period_end == date(2026, 10, 3)
        assert cal.prior_period_end == date(2026, 9, 26)
        assert cal.deduction_dates == [date(2026, 9, 28), date(2026, 9, 30), date(2026, 10, 1)]
        assert cal.first_pay_date == date(2026, 10, 16)
        assert cal.first_pay_date.weekday() == 4  # Friday
        assert [cal.pay_date(n) for n in (1, 2, 3)] == [
            date(2026, 10, 16), date(2026, 10, 30), date(2026, 11, 13)]

    def test_recording_calendar(self):
        cal = rules.pay_calendar(date(2026, 9, 1))
        assert cal.period_end == date(2026, 8, 29)
        assert cal.deduction_dates == [date(2026, 8, 24), date(2026, 8, 26), date(2026, 8, 27)]
        assert cal.first_pay_date == date(2026, 9, 11)
        assert cal.pay_date(3) == date(2026, 10, 9)

    def test_pay_date_rejects_zero(self):
        with pytest.raises(ValueError):
            rules.pay_calendar(date(2026, 10, 8)).pay_date(0)

    def test_add_business_days_skips_weekend(self):
        assert rules.add_business_days(date(2026, 10, 8), 3) == date(2026, 10, 13)


class TestDisplayStrings:

    @pytest.mark.parametrize("n, s", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"),
                                      (11, "11th"), (12, "12th"), (13, "13th"),
                                      (21, "21st"), (22, "22nd"), (23, "23rd"), (31, "31st")])
    def test_ordinals(self, n, s):
        assert rules.ordinal_en(n) == s

    def test_dates(self):
        assert rules.date_display_en(date(2026, 10, 16)) == "Friday, October 16th"
        assert rules.date_display_es(date(2026, 10, 16)) == "viernes 16 de octubre"
        assert rules.date_display_en(date(2026, 9, 11)) == "Friday, September 11th"
        assert rules.date_display_es(date(2026, 8, 29)) == "sábado 29 de agosto"

    def test_days_list_across_months(self):
        days = [date(2026, 9, 28), date(2026, 9, 30), date(2026, 10, 1)]
        assert rules.days_display_en(days) == "Monday the 28th, Wednesday the 30th and Thursday, October 1st"
        assert rules.days_display_es(days) == "lunes 28, miércoles 30 de septiembre y jueves 1 de octubre"

    def test_days_list_one_month(self):
        days = [date(2026, 8, 27), date(2026, 8, 24), date(2026, 8, 26)]
        assert rules.days_display_en(days) == "Monday the 24th, Wednesday the 26th and Thursday the 27th"
        assert rules.days_display_es(days) == "lunes 24, miércoles 26 y jueves 27 de agosto"

    def test_days_list_short_forms(self):
        assert rules.days_display_en([]) == ""
        assert rules.days_display_es([]) == ""
        assert rules.days_display_en([date(2026, 9, 28)]) == "Monday the 28th"
        assert rules.days_display_es([date(2026, 9, 28)]) == "lunes 28 de septiembre"

    @pytest.mark.parametrize("value, en, es", [
        (Decimal("41.625"), "$41.63", "41 dólares con 63 centavos"),
        (27.75, "$27.75", "27 dólares con 75 centavos"),
        (165, "$165.00", "165 dólares"),
        (1.01, "$1.01", "1 dólar con 1 centavo"),
        (1234.5, "$1,234.50", "1234 dólares con 50 centavos"),
    ])
    def test_amounts(self, value, en, es):
        assert rules.amount_display_en(value) == en
        assert rules.amount_display_es(value) == es

    def test_money_rounds_half_up(self):
        assert rules.money(41.625) == Decimal("41.63")
        assert rules.money("0.005") == Decimal("0.01")

    @pytest.mark.parametrize("d, en, es", [
        (date(2026, 11, 13), "mid-November", "mediados de noviembre"),
        (date(2026, 10, 9), "mid-October", "mediados de octubre"),
        (date(2026, 10, 2), "early October", "principios de octubre"),
        (date(2026, 10, 30), "late October", "finales de octubre"),
        (date(2026, 10, 21), "mid-October", "mediados de octubre"),
        (date(2026, 10, 22), "late October", "finales de octubre"),
    ])
    def test_target_labels(self, d, en, es):
        assert rules.target_label_en(d) == en
        assert rules.target_label_es(d) == es


class TestOvertimePricing:

    def test_daniel(self):
        p = rules.price_restored_hours(1.5, 43.0, "18.50")
        assert p.amount_usd == Decimal("41.63")
        assert p.ot_rate_usd == Decimal("27.75")
        assert p.overtime is True and p.ot_hours == 1.5 and p.regular_hours == 0

    def test_partial_two_days(self):
        p = rules.price_restored_hours(1.0, 43.0, 18.50)
        assert p.amount_usd == Decimal("27.75")

    def test_no_overtime_week_pays_base(self):
        p = rules.price_restored_hours(1.0, 40.0, 18.50)
        assert p.overtime is False and p.amount_usd == Decimal("18.50")

    def test_mixed_regular_and_overtime(self):
        p = rules.price_restored_hours(2.0, 41.0, 20)
        assert (p.ot_hours, p.regular_hours) == (1.0, 1.0)
        assert p.amount_usd == Decimal("50.00")

    def test_ot_rate(self):
        assert rules.ot_rate("17.25") == Decimal("25.88")


class TestTimecardDays:

    def test_hours_and_discrepancy(self):
        day = rules.TimecardDay(date(2026, 9, 28), (("07:00", "16:00"),), 30, False)
        assert day.hours_worked == 9.0 and day.is_discrepancy
        clean = rules.TimecardDay(date(2026, 9, 29), (("07:00", "11:00"), ("11:30", "15:30")))
        assert clean.hours_worked == 8.0 and not clean.is_discrepancy

    def test_hours_short_filters_dates(self):
        days = [rules.TimecardDay(date(2026, 9, d), (("07:00", "16:00"),), 30, False) for d in (28, 30)]
        assert rules.hours_short(days) == 1.0
        assert rules.hours_short(days, [date(2026, 9, 28)]) == 0.5


class TestPayCorrectionRule:

    def test_under_four_hours_regular_paycheck(self):
        d = rules.evaluate_pay_correction(1.5, rules.pay_calendar(date(2026, 10, 8)))
        assert d.off_cycle is False and d.pay_date == date(2026, 10, 16)
        assert d.rule_id == "PAY-CORRECTIONS v2.4" and d.off_cycle_threshold_hours == 4

    def test_four_hours_or_more_off_cycle(self):
        d = rules.evaluate_pay_correction(4.0, rules.pay_calendar(date(2026, 10, 8)))
        assert d.off_cycle is True and d.pay_date == date(2026, 10, 13)


class TestPtoProjection:

    def test_daniel_demo(self):
        cal = rules.pay_calendar(date(2026, 10, 8))
        p = rules.project_time_off(62.5, 6.15, 80, cal)
        assert (p.hours_needed, p.periods_needed, p.already_enough) == (17.5, 3, False)
        assert p.target_pay_date == date(2026, 11, 13)

    def test_daniel_recording(self):
        p = rules.project_time_off(62.5, 6.15, 80, rules.pay_calendar(date(2026, 9, 1)))
        assert p.target_pay_date == date(2026, 10, 9)
        assert rules.target_label_en(p.target_pay_date) == "mid-October"

    def test_already_enough(self):
        p = rules.project_time_off(88.5, 6.15, 80, rules.pay_calendar(date(2026, 10, 8)))
        assert p.already_enough and p.periods_needed == 0 and p.target_pay_date is None

    def test_exact_multiple(self):
        p = rules.project_time_off(0, 5.0, 10, rules.pay_calendar(date(2026, 10, 8)))
        assert p.periods_needed == 2

    def test_accrual_must_be_positive(self):
        with pytest.raises(ValueError):
            rules.project_time_off(1, 0, 10, rules.pay_calendar(date(2026, 10, 8)))

    def test_hours_to_days(self):
        assert rules.hours_to_days(62.5) == 7.8
        assert rules.hours_to_days(80) == 10.0


class TestIdentifiers:

    @pytest.mark.parametrize("cid, mobile, expected", [
        ("774-2318", "", ("colleague_id", "7742318")),
        ("ID 774 2318", "", ("colleague_id", "7742318")),
        ("", "(602) 555-0148", ("mobile", "6025550148")),
        ("", "+1 602 555 0148", ("mobile", "6025550148")),
        ("602-555-0148", "", ("mobile", "6025550148")),   # mobile said as an ID
        ("", "7742318", ("colleague_id", "7742318")),      # ID said as a mobile
        ("774-231", "", ("invalid", "774231")),
        ("", "", ("invalid", "")),
    ])
    def test_classify(self, cid, mobile, expected):
        assert rules.classify_identifier(cid, mobile) == expected

    def test_masking(self):
        assert rules.mask_digits("774-2318") == "*****18"
        assert rules.mask_digits("") == ""
        assert rules.mask_digit_runs("tried 774-2381, then (602) 555-0199 at 3pm") == \
            "tried *****81, then (********99 at 3pm"
        assert rules.mask_digit_runs("") == ""


class TestSpokenDigits:

    @pytest.mark.parametrize("text, digits", [
        ("seven seven four two three one eight", "7742318"),
        ("my ID is seven seven four, two three one eight", "7742318"),
        ("Seven-seven-four, two-three-one-eight", "7742318"),
        ("six oh two, double five five, oh one four eight", "6025550148"),
        ("six zero two five five five zero one four eight", "6025550148"),
        ("triple five", "555"),
        ("siete siete cuatro dos tres uno ocho", "7742318"),
        ("seis cero dos, doble cinco cinco, cero uno cuatro ocho", "6025550148"),
        ("774 two three one eight", "7742318"),
        ("Oh, it's 774-2318", "7742318"),            # leading "oh" is not a zero
        ("this one is 774-2318", "7742318"),         # an isolated spoken digit is ignored
        ("double", ""), ("seven", ""), ("", ""), (None, ""),
    ])
    def test_digits_only(self, text, digits):
        assert rules.digits_only(text) == digits

    def test_classify_spoken_id_and_mobile(self):
        assert rules.classify_identifier("seven seven four two three one eight", "") == \
            ("colleague_id", "7742318")
        assert rules.classify_identifier("", "six oh two five five five oh one four eight") == \
            ("mobile", "6025550148")
        assert rules.classify_identifier("siete siete cuatro dos tres uno ocho", "") == \
            ("colleague_id", "7742318")


class TestNumberDisplays:

    @pytest.mark.parametrize("value, en, es", [
        (1.5, "an hour and a half", "una hora y media"),
        (0.5, "half an hour", "media hora"),
        (1.0, "one hour", "una hora"),
        (5.0, "five hours", "cinco horas"),
        (2.5, "two and a half hours", "dos horas y media"),
        (0, "zero hours", "cero horas"),
        (25, "25 hours", "veinticinco horas"),
        (1.25, "1.25 hours", "1.25 horas"),
    ])
    def test_hours(self, value, en, es):
        assert rules.hours_display_en(value) == en
        assert rules.hours_display_es(value) == es

    @pytest.mark.parametrize("value, en, es", [
        (17.5, "17 and a half", "diecisiete y media"), (3, "3", "tres"),
        (0.5, "a half", "media"), (45, "45", "cuarenta y cinco"), (1.25, "1.25", "1.25"),
        (40, "40", "cuarenta")])
    def test_quantities(self, value, en, es):
        assert rules.quantity_display_en(value) == en
        assert rules.quantity_display_es(value) == es

    def test_number_words_and_plain_numbers(self):
        assert (rules.number_word_en(3), rules.number_word_es(3)) == ("three", "tres")
        assert (rules.number_word_en(21), rules.number_word_es(100)) == ("21", "100")
        assert [rules.number_display(v) for v in (62.5, 7.8, 6.15, 80.0, 80)] == \
            ["62.5", "7.8", "6.15", "80", "80"]
        assert (rules.yes_no(True), rules.yes_no(0)) == ("yes", "no")


def test_group_digits():
    assert rules.group_digits("774231") == "774-231"
    assert rules.group_digits("seven seven four") == "774"
    assert rules.group_digits("") == ""
