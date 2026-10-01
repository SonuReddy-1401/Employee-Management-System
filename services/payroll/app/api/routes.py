from typing import Dict, Any, List
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.errors import EMSError
from ems_common.security import get_current_user, require_roles
from services.payroll.app.domain.payroll import (
    calculate_payslip,
    count_unpaid_days_in_month,
    count_weekdays_in_month,
    parse_month,
)
from services.payroll.app.models.payroll import PayrollProfile, Payslip
from services.payroll.app.repositories.payroll_repository import PayrollRepository
from services.payroll.app.schemas.payroll import (
    PayrollRunResponse,
    PayslipResponse,
    ProfileCreateRequest,
    ProfileResponse,
)

router = APIRouter()


async def get_db():
    raise NotImplementedError("Replaced in main app dependency override")


@router.post("/internal/profiles", response_model=ProfileResponse)
async def create_profile(payload: ProfileCreateRequest, db: AsyncSession = Depends(get_db)):
    repo = PayrollRepository(db)
    existing = await repo.get_profile(payload.employee_id)
    if existing:
        if existing.monthly_salary == payload.monthly_salary:
            return existing
        else:
            raise EMSError(
                code="CONFLICT",
                message="Profile exists with a different salary",
                status_code=status.HTTP_409_CONFLICT,
            )

    profile = PayrollProfile(
        employee_id=payload.employee_id,
        monthly_salary=payload.monthly_salary,
    )
    created_profile = await repo.create_profile(profile)
    return Response(
        content=ProfileResponse.model_validate(created_profile).model_dump_json(),
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
    )


@router.delete("/internal/profiles/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(employee_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = PayrollRepository(db)
    await repo.delete_profile(employee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/payroll/run",
    response_model=PayrollRunResponse,
    dependencies=[Depends(require_roles("HR", "ADMIN"))],
)
async def run_payroll(
    month: str = Query(..., description="Month in YYYY-MM format"),
    db: AsyncSession = Depends(get_db),
):
    year, m = parse_month(month)
    working_days = count_weekdays_in_month(year, m)

    repo = PayrollRepository(db)
    profiles = await repo.list_all_profiles()

    created_count = 0
    skipped_count = 0

    for profile in profiles:
        existing_payslip = await repo.get_payslip(profile.employee_id, month)
        if existing_payslip:
            skipped_count += 1
            continue

        deductions = await repo.list_leave_deductions_for_employee(profile.employee_id)
        unpaid_days = sum(
            count_unpaid_days_in_month(d.start_date, d.end_date, year, m)
            for d in deductions
            if d.leave_type == "UNPAID"
        )

        gross, deduction, net = calculate_payslip(profile.monthly_salary, working_days, unpaid_days)

        payslip = Payslip(
            id=uuid4(),
            employee_id=profile.employee_id,
            month=month,
            gross_salary=gross,
            unpaid_leave_days=unpaid_days,
            deduction=deduction,
            net_salary=net,
        )
        await repo.create_payslip(payslip)
        created_count += 1

    return PayrollRunResponse(month=month, created=created_count, skipped=skipped_count)


@router.get("/payslips/{employee_id}", response_model=List[PayslipResponse])
async def get_payslips(
    employee_id: UUID,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_role = user.get("role")
    user_id = user.get("user_id")

    if user_role in ["MANAGER", "EMPLOYEE"] and user_id != str(employee_id):
        raise EMSError(
            code="FORBIDDEN",
            message="Access denied to payslips for another employee",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    repo = PayrollRepository(db)
    payslips = await repo.list_payslips_by_employee(employee_id)
    return payslips
