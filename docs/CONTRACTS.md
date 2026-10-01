# Service Contracts & System Specification

## Ports

| Service | Port |
| :--- | :--- |
| Gateway | `8000` |
| Auth | `8001` |
| Employee | `8002` |
| Leave | `8003` |
| Payroll | `8004` |
| Notification | `8005` |

---

## Roles & JWT Claims

- **Roles**: `ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`
- **JWT Claims**:
  - `sub`: User ID
  - `role`: User Role (`ADMIN` | `HR` | `MANAGER` | `EMPLOYEE`)
  - `exp`: Token Expiration Timestamp

---

## Per-Service Endpoints

### Auth Service (`:8001`)
| Method | Endpoint | Description / Payload |
| :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticates user; Returns `{"access_token": "..."}` |
| `POST` | `/internal/users` | Creates user credentials (HR/ADMIN or internal call) |
| `DELETE` | `/internal/users/{id}` | Deletes user credentials (compensation endpoint) |

#### Payload details
- `POST /auth/login` body `{email, password}` -> 200 `{access_token, token_type:"bearer"}`; 401 on wrong email or password (same message for both, do not reveal which).
- `POST /internal/users` body `{id (uuid, equals the employee id), email, password, role}` -> 201 `{id, email, role}`; 409 if id or email already exists; 422 on invalid input (role must be one of ADMIN, HR, MANAGER, EMPLOYEE; password minimum length 8).
- `DELETE /internal/users/{id}` -> 204 always, even if the user does not exist (compensation must be safe to repeat).
- `/internal/*` endpoints need no JWT because the gateway blocks them from outside the network.

### Employee Service (`:8002`)
| Method | Endpoint | Description / Payload |
| :--- | :--- | :--- |
| `POST` | `/employees` | Onboards employee; Returns employee record |
| `GET` | `/employees` | Lists employees (supports filter/pagination) |
| `GET` | `/employees/{id}` | Gets single employee record |
| `PUT` | `/employees/{id}` | Update employee record by ID |
| `DELETE` | `/employees/{id}` | Soft deletes employee |

#### Payload details
- Employee id is a server-generated uuid.
- `POST /employees` body `{name, email, department, designation, manager_id (optional uuid), role (ADMIN|HR|MANAGER|EMPLOYEE, default EMPLOYEE), initial_password (min 8 chars), monthly_salary (positive decimal)}`. The last three are saga inputs: they are validated here but NEVER stored in the employee table and NEVER returned. For now (before the saga exists) it returns 201 with the employee in status `PENDING_ONBOARDING`. 409 if email already exists; 422 on invalid input or if manager_id does not refer to an existing non-deleted employee.
- Employee response fields: `id`, `name`, `email`, `department`, `designation`, `manager_id`, `status`, `created_at`, `updated_at`.
- `GET /employees` supports query params `page` (default 1), `page_size` (default 20, max 100) and optional `department` filter; response `{items, total, page, page_size}`. Soft-deleted employees are excluded.
- `GET /employees/{id}` -> 404 if missing or soft-deleted.
- `PUT /employees/{id}` body: any of `{name, email, department, designation, manager_id}`; status can NOT be changed through PUT. 404 if missing, 409 on duplicate email, 422 if manager_id equals the employee's own id or refers to a non-existing employee.
- `DELETE /employees/{id}` -> soft delete (`deleted_at` timestamp), 204; repeating it also returns 204; 404 only if the id never existed.
- Access: all write endpoints require role `HR` or `ADMIN`; GET endpoints require any valid JWT. Missing/invalid token 401, wrong role 403.

#### Fields
`id`, `name`, `email` (unique), `department`, `designation`, `manager_id`, `status`

#### Status Transitions
`PENDING_ONBOARDING` -> `ACTIVE` | `ONBOARDING_FAILED`

### Leave Service (`:8003`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/leaves` | Create leave request |
| `POST` | `/leaves/{id}/approve` | Approve leave request |
| `POST` | `/leaves/{id}/reject` | Reject leave request |
| `POST` | `/leaves/{id}/cancel` | Cancel leave request |
| `GET` | `/leaves` | List leave requests |
| `GET` | `/leaves/balance/{employee_id}` | Get leave balance for an employee |

### Payroll Service (`:8004`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/internal/profiles` | Create payroll profile |
| `DELETE` | `/internal/profiles/{employee_id}` | Delete payroll profile (compensation) |
| `POST` | `/payroll/run?month=YYYY-MM` | Process payroll for given month |
| `GET` | `/payslips/{employee_id}` | Get payslips for an employee |

#### Payload details
- `POST /internal/profiles` body `{employee_id (uuid), monthly_salary (positive decimal)}` -> 201 `{employee_id, monthly_salary}`. Idempotent: if a profile for that employee_id already exists with the same salary, return 200 with the same body; if it exists with a different salary, return 409. 422 on invalid input.
- `DELETE /internal/profiles/{employee_id}` -> 204 always, even if missing (safe to repeat).
- `/internal/*` needs no JWT (gateway blocks it externally).
- `POST /payroll/run?month=YYYY-MM` requires role HR or ADMIN. 422 if month is malformed. For every profile it creates one payslip for that month; if a payslip for `(employee_id, month)` already exists it is skipped, never duplicated. Response 200 `{month, created, skipped}`.
- Payslip fields: `id`, `employee_id`, `month`, `gross_salary`, `unpaid_leave_days`, `deduction`, `net_salary`, `created_at`.
- `GET /payslips/{employee_id}`: HR and ADMIN may read any employee; MANAGER and EMPLOYEE only their own (JWT sub must equal employee_id, otherwise 403). Returns a list ordered by month descending; empty list if none. 401 without a valid token.
- Calculation: working days = Monday to Friday days in that month. unpaid_leave_days = number of Monday-Friday days of UNPAID leave that fall inside the month (a leave spanning two months counts only the days inside each month). deduction = gross_salary / working_days_in_month * unpaid_leave_days. net_salary = gross_salary - deduction. All money uses Decimal, rounded to 2 decimals with ROUND_HALF_UP. Never use float for money.

### Notification Service (`:8005`)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/notifications/{employee_id}` | Get notifications for an employee |
- Consumes events, stores notification rows, and logs a simulated email.

---

## Onboarding Saga

Orchestrated inside the **Employee** service on `POST /employees`:
1. Save employee as `PENDING_ONBOARDING`.
2. Call Auth service (`POST /internal/users`) to create user credentials.
3. Call Payroll service (`POST /internal/profiles`) to create payroll profile.
4. Mark status as `ACTIVE` and write outbox event `EmployeeOnboarded`.

**Failure Compensation**:
- If any step fails: compensate completed steps in reverse order (`DELETE /internal/users/{id}`, `DELETE /internal/profiles/{employee_id}`), mark status as `ONBOARDING_FAILED`, and return status `502`.

---

## Leave State Machine

- **Valid State Transitions**:
  - `PENDING` -> `APPROVED` | `REJECTED` | `CANCELLED`
  - `APPROVED` -> `CANCELLED`
- All other state transitions return HTTP status `409`.
- **Validation**: Validates that the employee exists via the Employee service, cached in Redis (TTL 60s).

---

## Payroll Salary Calculation

- Unpaid-leave days (derived from `LeaveApproved` events) reduce salary.

---

## Events & Messaging

- **Exchange**: RabbitMQ topic exchange `"ems.events"`
- **Envelope Structure**:
  - `event_id` (`uuid`)
  - `type` (`string`)
  - `occurred_at` (`timestamp`)
  - `correlation_id` (`uuid`)
  - `payload` (`object`)
- **Event Types**:
  - `EmployeeOnboarded`
  - `LeaveRequested`
  - `LeaveApproved`
  - `LeaveRejected`
- **Outbox Pattern**: Producers write event row in the same DB transaction; a background publisher sends it.
- **Idempotency**: Consumers are idempotent via a `processed_events` table keyed by `event_id`.

#### Event payloads
- `EmployeeOnboarded` payload `{employee_id, name, email}`
- `LeaveRequested`, `LeaveApproved`, `LeaveRejected` payload `{leave_id, employee_id, start_date (ISO date), end_date (ISO date), leave_type (PAID|UNPAID), days}`, where `days` = number of Monday-Friday days from `start_date` to `end_date` inclusive.

---

## Cross-Cutting Concerns

- **Header Propagation**: Header `X-Correlation-ID` is generated at the Gateway and propagated in all HTTP calls and async events.
- **Health & Metrics**: `/health` and `/metrics` implemented on every service.
- **Resilience**: Synchronous service calls use timeout + `tenacity` retry + `pybreaker` circuit breaker.
