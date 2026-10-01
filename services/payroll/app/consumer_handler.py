import logging
from datetime import date
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.events import EventEnvelope, EventType
from services.payroll.app.models.payroll import CancelledLeave, LeaveDeduction

logger = logging.getLogger(__name__)


async def handle_payroll_event(session: AsyncSession, envelope: EventEnvelope) -> None:
    if envelope.type not in (EventType.LEAVE_APPROVED, EventType.LEAVE_CANCELLED):
        logger.info(f"Payroll consumer ignoring unrelated event type: {envelope.type}")
        return

    payload = envelope.payload
    leave_id_str = payload.get("leave_id")
    if not leave_id_str:
        logger.warning(f"Payroll event payload missing leave_id: {payload}")
        return

    leave_id = UUID(str(leave_id_str))

    if envelope.type == EventType.LEAVE_CANCELLED:
        # 1. Record leave as cancelled (if not already recorded)
        stmt_cancelled = select(CancelledLeave).where(CancelledLeave.leave_id == leave_id)
        res_cancelled = await session.execute(stmt_cancelled)
        if not res_cancelled.scalar_one_or_none():
            session.add(CancelledLeave(leave_id=leave_id))

        # 2. Delete any existing deduction for this leave_id
        stmt_deduction = select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id)
        res_deduction = await session.execute(stmt_deduction)
        deduction = res_deduction.scalar_one_or_none()
        if deduction:
            await session.delete(deduction)
        logger.info(f"Processed LeaveCancelled for leave_id {leave_id}")

    elif envelope.type == EventType.LEAVE_APPROVED:
        # Check if this leave was already cancelled (out-of-order execution)
        stmt_cancelled = select(CancelledLeave).where(CancelledLeave.leave_id == leave_id)
        res_cancelled = await session.execute(stmt_cancelled)
        if res_cancelled.scalar_one_or_none():
            logger.info(f"Leave {leave_id} was previously cancelled. Skipping LeaveApproved deduction.")
            return

        leave_type = payload.get("leave_type")
        if leave_type == "UNPAID":
            emp_id = UUID(str(payload["employee_id"]))
            start_date = date.fromisoformat(payload["start_date"])
            end_date = date.fromisoformat(payload["end_date"])

            # Ensure uniqueness per leave_id
            stmt_deduction = select(LeaveDeduction).where(LeaveDeduction.leave_id == leave_id)
            res_deduction = await session.execute(stmt_deduction)
            if not res_deduction.scalar_one_or_none():
                deduction = LeaveDeduction(
                    employee_id=emp_id,
                    leave_id=leave_id,
                    start_date=start_date,
                    end_date=end_date,
                    leave_type=leave_type,
                )
                session.add(deduction)
                logger.info(f"Added LeaveDeduction for unpaid leave {leave_id}")
