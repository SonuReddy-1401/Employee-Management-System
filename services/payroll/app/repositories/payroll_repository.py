from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.payroll.app.models.payroll import LeaveDeduction, PayrollProfile, Payslip


class PayrollRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, employee_id: UUID) -> Optional[PayrollProfile]:
        stmt = select(PayrollProfile).where(PayrollProfile.employee_id == employee_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_profile(self, profile: PayrollProfile) -> PayrollProfile:
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def delete_profile(self, employee_id: UUID) -> None:
        profile = await self.get_profile(employee_id)
        if profile:
            await self.db.delete(profile)
            await self.db.commit()

    async def list_all_profiles(self) -> List[PayrollProfile]:
        stmt = select(PayrollProfile)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_payslip(self, employee_id: UUID, month: str) -> Optional[Payslip]:
        stmt = select(Payslip).where(Payslip.employee_id == employee_id, Payslip.month == month)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_payslip(self, payslip: Payslip) -> Payslip:
        self.db.add(payslip)
        await self.db.commit()
        await self.db.refresh(payslip)
        return payslip

    async def list_payslips_by_employee(self, employee_id: UUID) -> List[Payslip]:
        stmt = (
            select(Payslip)
            .where(Payslip.employee_id == employee_id)
            .order_by(Payslip.month.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_leave_deductions_for_employee(self, employee_id: UUID) -> List[LeaveDeduction]:
        stmt = select(LeaveDeduction).where(LeaveDeduction.employee_id == employee_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
