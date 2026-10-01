from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.errors import EMSError
from ems_common.security import get_current_user, require_roles
from services.employee.app.domain.employee import (
    compute_pagination,
    extract_updatable_fields,
    validate_manager_not_self,
)
from services.employee.app.domain.saga import OnboardingSaga
from services.employee.app.repositories.employee_repository import EmployeeRepository
from services.employee.app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdateRequest,
)

router = APIRouter()


async def get_db():
    raise NotImplementedError("Replaced in main app dependency override")


@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("HR", "ADMIN"))],
)
async def create_employee(payload: EmployeeCreateRequest, db: AsyncSession = Depends(get_db)):
    repo = EmployeeRepository(db)

    # Check manager validity if manager_id is specified
    if payload.manager_id:
        manager = await repo.get_by_id(payload.manager_id)
        if not manager:
            raise EMSError(
                code="VALIDATION_ERROR",
                message="Manager does not exist or has been deleted",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    # Check duplicate email
    existing_email = await repo.get_by_email(payload.email)
    if existing_email:
        raise EMSError(
            code="CONFLICT",
            message="Employee with this email already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    saga = OnboardingSaga(db)
    created_employee = await saga.execute(payload)
    return created_employee


@router.get(
    "/employees",
    response_model=EmployeeListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = EmployeeRepository(db)
    offset, limit = compute_pagination(page, page_size)
    items, total = await repo.list_paginated(offset=offset, limit=limit, department=department)

    return EmployeeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=limit,
    )


@router.get(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_employee(employee_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = EmployeeRepository(db)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise EMSError(
            code="NOT_FOUND",
            message="Employee not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return employee


@router.put(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_roles("HR", "ADMIN"))],
)
async def update_employee(
    employee_id: UUID, payload: EmployeeUpdateRequest, db: AsyncSession = Depends(get_db)
):
    repo = EmployeeRepository(db)
    employee = await repo.get_by_id(employee_id)
    if not employee:
        raise EMSError(
            code="NOT_FOUND",
            message="Employee not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    update_data = extract_updatable_fields(payload.model_dump(exclude_unset=True))

    if "manager_id" in update_data:
        new_manager_id = update_data["manager_id"]
        if new_manager_id is not None:
            validate_manager_not_self(employee_id, new_manager_id)
            manager = await repo.get_by_id(new_manager_id)
            if not manager:
                raise EMSError(
                    code="VALIDATION_ERROR",
                    message="Manager does not exist or has been deleted",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

    if "email" in update_data and update_data["email"] != employee.email:
        existing_email = await repo.get_by_email(update_data["email"])
        if existing_email:
            raise EMSError(
                code="CONFLICT",
                message="Employee with this email already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    updated_employee = await repo.update(employee, update_data)
    return updated_employee


@router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("HR", "ADMIN"))],
)
async def delete_employee(employee_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = EmployeeRepository(db)
    employee = await repo.get_by_id_including_deleted(employee_id)
    if not employee:
        raise EMSError(
            code="NOT_FOUND",
            message="Employee not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    await repo.soft_delete(employee)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
