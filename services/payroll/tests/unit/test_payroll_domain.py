from datetime import date
from decimal import Decimal
import pytest
from ems_common.errors import EMSError
from services.payroll.app.domain.payroll import (
    calculate_payslip,
    count_unpaid_days_in_month,
    count_weekdays_in_month,
    parse_month,
)


def test_parse_month_valid_and_invalid():
    assert parse_month("2026-10") == (2026, 10)
    assert parse_month("2024-02") == (2024, 2)

    with pytest.raises(EMSError) as exc_info:
        parse_month("invalid-month")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"

    with pytest.raises(EMSError):
        parse_month("2024/02")


def test_weekdays_in_normal_and_leap_february():
    # March 2024 has 31 days (21 weekdays)
    assert count_weekdays_in_month(2024, 3) == 21

    # February 2024 (leap year: 29 days, Feb 1 = Thursday) -> 21 weekdays
    assert count_weekdays_in_month(2024, 2) == 21

    # February 2025 (non-leap year: 28 days, Feb 1 = Saturday) -> 20 weekdays
    assert count_weekdays_in_month(2025, 2) == 20


def test_unpaid_days_inside_month():
    # 2024-03-11 (Mon) to 2024-03-15 (Fri) -> 5 days
    days = count_unpaid_days_in_month(date(2024, 3, 11), date(2024, 3, 15), 2024, 3)
    assert days == 5


def test_unpaid_days_spanning_two_months():
    start = date(2024, 3, 28)  # Thu
    end = date(2024, 4, 5)  # Fri (next month)

    # In March 2024: 2024-03-28 (Thu), 2024-03-29 (Fri) -> 2 days
    march_days = count_unpaid_days_in_month(start, end, 2024, 3)
    assert march_days == 2

    # In April 2024: Apr 1 (Mon) to Apr 5 (Fri) -> 5 days
    april_days = count_unpaid_days_in_month(start, end, 2024, 4)
    assert april_days == 5


def test_unpaid_days_weekend_only():
    # 2024-03-09 (Sat) to 2024-03-10 (Sun) -> 0 days
    days = count_unpaid_days_in_month(date(2024, 3, 9), date(2024, 3, 10), 2024, 3)
    assert days == 0


def test_calculate_payslip_zero_unpaid():
    salary = Decimal("5000.00")
    gross, deduction, net = calculate_payslip(salary, 22, 0)
    assert isinstance(gross, Decimal)
    assert isinstance(deduction, Decimal)
    assert isinstance(net, Decimal)
    assert gross == Decimal("5000.00")
    assert deduction == Decimal("0.00")
    assert net == Decimal("5000.00")


def test_calculate_payslip_full_unpaid():
    salary = Decimal("5000.00")
    gross, deduction, net = calculate_payslip(salary, 22, 22)
    assert gross == Decimal("5000.00")
    assert deduction == Decimal("5000.00")
    assert net == Decimal("0.00")


def test_calculate_payslip_rounding_half_up():
    salary = Decimal("5000.00")
    # 5000 / 22 * 3 = 681.818181... -> rounds HALF_UP to 681.82
    gross, deduction, net = calculate_payslip(salary, 22, 3)
    assert gross == Decimal("5000.00")
    assert deduction == Decimal("681.82")
    assert net == Decimal("4318.18")
    assert isinstance(gross, Decimal)
    assert isinstance(deduction, Decimal)
    assert isinstance(net, Decimal)
