import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from ems_common.correlation import get_correlation_id
from ems_common.errors import EMSError
from ems_common.http_client import ResilientHTTPClient
from services.employee.app.config import settings
from services.employee.app.models.employee import Employee, OutboxMessage
from services.employee.app.schemas.employee import EmployeeCreateRequest

logger = logging.getLogger(__name__)


class OnboardingSaga:
    def __init__(self, db: AsyncSession, http_client: ResilientHTTPClient | None = None):
        self.db = db
        self.http_client = http_client or ResilientHTTPClient()

    async def execute(self, payload: EmployeeCreateRequest) -> Employee:
        emp_id = uuid4()

        # Step 1: Validate input, insert as PENDING_ONBOARDING and COMMIT
        employee = Employee(
            id=emp_id,
            name=payload.name,
            email=payload.email,
            department=payload.department,
            designation=payload.designation,
            manager_id=payload.manager_id,
            status="PENDING_ONBOARDING",
        )
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)

        auth_completed = False
        payroll_completed = False
        saga_failed = False

        role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)

        # Step 2: Call Auth POST /internal/users
        try:
            auth_url = f"{settings.AUTH_SERVICE_URL}/internal/users"
            auth_resp = await self.http_client.post(
                auth_url,
                json={
                    "id": str(emp_id),
                    "email": payload.email,
                    "password": payload.initial_password,
                    "role": role_str,
                },
            )
            if not auth_resp.is_success:
                saga_failed = True
            else:
                auth_completed = True
        except Exception as exc:
            logger.warning(f"Auth create user failed for employee {emp_id}: {exc}")
            saga_failed = True

        # Step 3: Call Payroll POST /internal/profiles (only if Auth succeeded)
        if not saga_failed:
            try:
                payroll_url = f"{settings.PAYROLL_SERVICE_URL}/internal/profiles"
                payroll_resp = await self.http_client.post(
                    payroll_url,
                    json={
                        "employee_id": str(emp_id),
                        "monthly_salary": float(payload.monthly_salary),
                    },
                )
                if not payroll_resp.is_success:
                    saga_failed = True
                else:
                    payroll_completed = True
            except Exception as exc:
                logger.warning(f"Payroll create profile failed for employee {emp_id}: {exc}")
                saga_failed = True

        # Step 4: If all succeeded, update status to ACTIVE & write Outbox event in ONE transaction
        if not saga_failed and auth_completed and payroll_completed:
            try:
                employee.status = "ACTIVE"
                employee.updated_at = datetime.now(timezone.utc)

                outbox_msg = OutboxMessage(
                    id=str(uuid4()),
                    event_type="EmployeeOnboarded",
                    payload=json.dumps(
                        {"employee_id": str(emp_id), "name": payload.name, "email": payload.email}
                    ),
                    correlation_id=get_correlation_id(),
                )
                self.db.add(outbox_msg)
                await self.db.commit()
                await self.db.refresh(employee)
                return employee
            except Exception as exc:
                logger.error(f"Failed to commit ACTIVE status / outbox row for employee {emp_id}: {exc}")
                saga_failed = True

        # Failure Compensation logic: reverse order (payroll first, then auth)
        if payroll_completed:
            try:
                comp_payroll_url = f"{settings.PAYROLL_SERVICE_URL}/internal/profiles/{emp_id}"
                await self.http_client.delete(comp_payroll_url)
            except Exception as comp_exc:
                logger.error(f"Compensation failed for Payroll employee_id={emp_id}: {comp_exc}")

        if auth_completed:
            try:
                comp_auth_url = f"{settings.AUTH_SERVICE_URL}/internal/users/{emp_id}"
                await self.http_client.delete(comp_auth_url)
            except Exception as comp_exc:
                logger.error(f"Compensation failed for Auth employee_id={emp_id}: {comp_exc}")

        # Set status to ONBOARDING_FAILED and commit
        employee.status = "ONBOARDING_FAILED"
        employee.updated_at = datetime.now(timezone.utc)
        await self.db.commit()

        raise EMSError(
            code="ONBOARDING_FAILED",
            message="Saga execution failed during onboarding",
            status_code=502,
        )
