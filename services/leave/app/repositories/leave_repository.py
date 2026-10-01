from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from services.leave.app.models.leave import Leave


class LeaveRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_leave(self, leave: Leave) -> Leave:
        self.session.add(leave)
        await self.session.flush()
        return leave

    async def get_by_id(self, leave_id: UUID) -> Optional[Leave]:
        stmt = select(Leave).where(Leave.id == leave_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id_for_update(self, leave_id: UUID) -> Optional[Leave]:
        stmt = select(Leave).where(Leave.id == leave_id).with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def find_overlapping_leaves(
        self, employee_id: UUID, start_date: date, end_date: date
    ) -> List[Leave]:
        stmt = select(Leave).where(
            Leave.employee_id == employee_id,
            Leave.status.in_(["PENDING", "APPROVED"]),
            Leave.start_date <= end_date,
            Leave.end_date >= start_date,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def sum_used_paid_days(self, employee_id: UUID, year: int) -> int:
        stmt = select(func.coalesce(func.sum(Leave.days), 0)).where(
            Leave.employee_id == employee_id,
            Leave.status == "APPROVED",
            Leave.leave_type == "PAID",
            extract("year", Leave.start_date) == year,
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    async def list_leaves(
        self,
        employee_id: Optional[UUID] = None,
        status: Optional[str] = None,
        user_role: str = "EMPLOYEE",
        user_sub: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Leave], int]:
        stmt = select(Leave)

        # Visibility filter based on role
        if user_role in ("HR", "ADMIN"):
            if employee_id:
                stmt = stmt.where(Leave.employee_id == employee_id)
        elif user_role == "MANAGER":
            if user_sub:
                stmt = stmt.where(
                    or_(Leave.manager_id == user_sub, Leave.employee_id == user_sub)
                )
                if employee_id:
                    stmt = stmt.where(Leave.employee_id == employee_id)
        else:  # EMPLOYEE
            if user_sub:
                stmt = stmt.where(Leave.employee_id == user_sub)

        if status:
            stmt = stmt.where(Leave.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Pagination
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Leave.created_at.desc()).offset(offset).limit(page_size)

        res = await self.session.execute(stmt)
        items = list(res.scalars().all())
        return items, total
