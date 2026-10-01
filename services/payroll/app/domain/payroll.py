import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.errors import EMSError
from ems_common.events import EventEnvelope
from services.payroll.app.models.payroll import LeaveDeduction, ProcessedEvent


def parse_month(month_str: str) -> Tuple[int, int]:
    try:
        dt = datetime.strptime(month_str, "%Y-%m")
        return dt.year, dt.month
    except (ValueError, TypeError):
        raise EMSError(
            code="VALIDATION_ERROR",
            message="Invalid month format, expected YYYY-MM",
            status_code=422,
        )


def count_weekdays_in_month(year: int, month: int) -> int:
    _, num_days = calendar.monthrange(year, month)
    count = 0
    for day in range(1, num_days + 1):
        if date(year, month, day).weekday() < 5:  # Monday to Friday
            count += 1
    return count


def count_unpaid_days_in_month(start_date: date, end_date: date, year: int, month: int) -> int:
    _, num_days = calendar.monthrange(year, month)
    first_of_month = date(year, month, 1)
    last_of_month = date(year, month, num_days)

    overlap_start = max(start_date, first_of_month)
    overlap_end = min(end_date, last_of_month)

    if overlap_start > overlap_end:
        return 0

    count = 0
    curr = overlap_start
    while curr <= overlap_end:
        if curr.weekday() < 5:
            count += 1
        curr += timedelta(days=1)

    return count


def calculate_payslip(
    monthly_salary: Decimal, working_days: int, unpaid_days: int
) -> Tuple[Decimal, Decimal, Decimal]:
    gross = Decimal(str(monthly_salary))
    unpaid = Decimal(str(unpaid_days))
    working = Decimal(str(working_days))

    two_places = Decimal("0.01")

    if unpaid <= 0:
        deduction = Decimal("0.00")
        net = gross
    elif unpaid >= working:
        deduction = gross
        net = Decimal("0.00")
    else:
        raw_deduction = (gross / working) * unpaid
        deduction = raw_deduction.quantize(two_places, rounding=ROUND_HALF_UP)
        net = gross - deduction

    return (
        gross.quantize(two_places, rounding=ROUND_HALF_UP),
        deduction.quantize(two_places, rounding=ROUND_HALF_UP),
        net.quantize(two_places, rounding=ROUND_HALF_UP),
    )


async def handle_leave_approved(session: AsyncSession, envelope: EventEnvelope | dict) -> None:
    if isinstance(envelope, dict):
        envelope = EventEnvelope(**envelope)

    event_id = envelope.event_id

    # Check if event was already processed
    stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        return

    payload = envelope.payload
    if payload.get("leave_type") == "UNPAID":
        deduction = LeaveDeduction(
            id=uuid4(),
            employee_id=UUID(str(payload["employee_id"])),
            leave_id=UUID(str(payload["leave_id"])),
            start_date=date.fromisoformat(str(payload["start_date"])),
            end_date=date.fromisoformat(str(payload["end_date"])),
            leave_type="UNPAID",
        )
        session.add(deduction)

    # Mark as processed
    processed_entry = ProcessedEvent(event_id=event_id)
    session.add(processed_entry)
    await session.commit()
