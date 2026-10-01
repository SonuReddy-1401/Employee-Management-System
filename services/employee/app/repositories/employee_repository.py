from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from services.employee.app.models.employee import Employee


class EmployeeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, employee_id: UUID) -> Optional[Employee]:
        stmt = select(Employee).where(Employee.id == employee_id, Employee.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_including_deleted(self, employee_id: UUID) -> Optional[Employee]:
        stmt = select(Employee).where(Employee.id == employee_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Employee]:
        stmt = select(Employee).where(Employee.email == email, Employee.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self, offset: int, limit: int, department: Optional[str] = None
    ) -> Tuple[List[Employee], int]:
        base_stmt = select(Employee).where(Employee.deleted_at.is_(None))
        if department:
            base_stmt = base_stmt.where(Employee.department == department)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        items_stmt = base_stmt.order_by(Employee.created_at.desc()).offset(offset).limit(limit)
        items_result = await self.db.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def create(self, employee: Employee) -> Employee:
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def update(self, employee: Employee, fields: dict) -> Employee:
        for key, value in fields.items():
            setattr(employee, key, value)
        employee.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def soft_delete(self, employee: Employee) -> None:
        if employee.deleted_at is None:
            employee.deleted_at = datetime.now(timezone.utc)
            await self.db.commit()
