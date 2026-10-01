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
- `POST /employees` body `{name, email, department, designation, manager_id (optional uuid), role (ADMIN|HR|MANAGER|EMPLOYEE, default EMPLOYEE), initial_password (min 8 chars), monthly_salary (positive decimal)}`. The last three are saga inputs: they are validated here but NEVER stored in the employee table and NEVER returned. `POST /employees` runs the onboarding saga. On success it returns 201 with the employee in status `ACTIVE`. On saga failure it returns 502 with the project error JSON (code `"ONBOARDING_FAILED"`), and the employee row remains with status `ONBOARDING_FAILED`. Reusing the email of an `ONBOARDING_FAILED` employee returns 409 (known limitation). 409 if email already exists; 422 on invalid input or if manager_id does not refer to an existing non-deleted employee. The saga calls Auth `POST /internal/users` with `{id = employee id, email, password = initial_password, role}` and Payroll `POST /internal/profiles` with `{employee_id, monthly_salary}`. Compensation calls are Auth `DELETE /internal/users/{id}` and Payroll `DELETE /internal/profiles/{employee_id}`. `EmployeeOnboarded` payload is `{employee_id, name, email}`.
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

#### Payload details
- Rules: `leave_type` `PAID` | `UNPAID`. `days` = Monday-Friday days from `start_date` to `end_date` inclusive. 422 if `end_date < start_date`, if the range crosses a calendar year, or if `days = 0` (weekend-only).
- `POST /leaves` body `{employee_id, start_date (ISO date string), end_date (ISO date string), leave_type (PAID|UNPAID), reason (optional string)}` -> 201 leave object. Leave fields: `id`, `employee_id`, `manager_id` (snapshot of employee's manager at creation, nullable), `start_date`, `end_date`, `leave_type`, `reason`, `days`, `status`, `decided_by` (nullable), `created_at`, `updated_at`.
  Access: EMPLOYEE and MANAGER can only create for themselves (`JWT sub == employee_id`), else 403. HR and ADMIN can create for anyone.
  The employee is validated by calling Employee service `GET /employees/{id}`, forwarding the caller's Authorization header and correlation id. Employee not found -> 422; employee exists but status is not `ACTIVE` -> 422; Employee service unreachable or circuit open -> 503 with code `EMPLOYEE_SERVICE_UNAVAILABLE`. Only successful `ACTIVE` lookups are cached in Redis for `EMPLOYEE_CACHE_TTL_SECONDS` (cached fields: `id`, `status`, `manager_id`). If Redis is unreachable, log a warning and call the Employee service directly (never fail request due to Redis).
  409 if the new range overlaps any of that employee's `PENDING` or `APPROVED` leaves. For `PAID` leave: 422 if `days > remaining paid balance` for the year (`UNPAID` leave skips balance check). Initial status `PENDING`. Writes `LeaveRequested` outbox event in the same transaction.
- State machine: `PENDING` -> `APPROVED` | `REJECTED` | `CANCELLED`, `APPROVED` -> `CANCELLED`. Every transition locks the leave row (`SELECT ... FOR UPDATE`) so concurrent decisions cannot both succeed. Invalid transition -> 409.
- `POST /leaves/{id}/approve` and `/reject`: roles MANAGER, HR, ADMIN. A MANAGER may act only if `leave.manager_id == JWT sub`, else 403. Nobody may approve or reject their own leave (`JWT sub == leave.employee_id`) -> 403. On approve of `PAID` leave, re-check balance; if insufficient -> 409. Sets `decided_by`. Writes `LeaveApproved` or `LeaveRejected` outbox event in the same transaction. 404 if the leave does not exist.
- `POST /leaves/{id}/cancel`: allowed for the leave's own employee (`JWT sub == leave.employee_id`), HR, ADMIN, else 403. `PENDING` -> `CANCELLED` writes NO event. `APPROVED` -> `CANCELLED` writes `LeaveCancelled` outbox event. 404 if not found.
- `GET /leaves` query params: `employee_id`, `status`, `page` (default 1), `page_size` (default 20, max 100); response `{items, total, page, page_size}`. HR and ADMIN see all. MANAGER sees leaves where `manager_id == sub OR employee_id == sub`. EMPLOYEE sees only their own (`employee_id` filter is forced to `sub`).
- `GET /leaves/balance/{employee_id}?year=YYYY` (default current year) -> `{employee_id, year, allowance, used, remaining}`. `allowance` = `ANNUAL_PAID_LEAVE_DAYS` from env. `used` = sum of `days` of `APPROVED` `PAID` leaves whose `start_date` is in that year. HR/ADMIN any employee; others only themselves (else 403).
- All endpoints need a valid JWT (401 otherwise).

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
  - `LeaveCancelled`
- **Outbox Pattern**: Producers write event row in the same DB transaction; a background publisher sends it.
- **Idempotency**: Consumers are idempotent via a `processed_events` table keyed by `event_id`.

#### Event payloads
- `EmployeeOnboarded` payload `{employee_id, name, email}`
- `LeaveRequested`, `LeaveApproved`, `LeaveRejected`, `LeaveCancelled` payload `{leave_id, employee_id, start_date (ISO date), end_date (ISO date), leave_type (PAID|UNPAID), days}`, where `days` = number of Monday-Friday days from `start_date` to `end_date` inclusive.

---

## Cross-Cutting Concerns

- **Header Propagation**: Header `X-Correlation-ID` is generated at the Gateway and propagated in all HTTP calls and async events.
- **Health & Metrics**: `/health` and `/metrics` implemented on every service.
- **Resilience**: Synchronous service calls use timeout + `tenacity` retry + `pybreaker` circuit breaker.

---

## Event Routing & Consumers

- **Exchange**: Producers publish events with the event type as the routing key on topic exchange `ems.events`.
- **Queues & DLQ**: Consumers use durable named queues (configured via environment variables), a dead-letter exchange (DLX), and a dead-letter queue (DLQ).
- **Retry Policy**: A failing message is retried up to `MAX_DELIVERY_ATTEMPTS` (default 3); after max attempts, it is routed to the DLQ without requeue. Malformed messages land in the DLQ immediately.
- **Idempotency**: Duplicate `event_id` values are acknowledged and skipped using the `processed_events` table.

### Payroll Event Consumption
- Consumes `LeaveApproved` and `LeaveCancelled`.
- `LeaveApproved` with `leave_type` `UNPAID` inserts a `leave_deductions` row (unique per `leave_id`); `PAID` does nothing.
- `LeaveCancelled` deletes the deduction row for that `leave_id` if present AND records the `leave_id` in `cancelled_leaves`, preventing any late or duplicate `LeaveApproved` event for a cancelled leave from inserting a deduction.

### Notification Service Contracts
- **Endpoints**:
  - `GET /notifications/{employee_id}?limit=50`: Returns list of notifications ordered by `created_at` descending (`id`, `employee_id`, `event_id`, `event_type`, `message`, `created_at`). `limit` parameter defaults to 50 (max 200).
- **Authorization**:
  - `HR` and `ADMIN` roles may read any employee's notifications.
  - Other roles (`EMPLOYEE`, `MANAGER`) can only read their own notifications (`token sub == employee_id`), else returns `403 FORBIDDEN`.
  - Unauthenticated requests return `401 UNAUTHORIZED`.
- **Event Consumption**:
  - Consumes `EmployeeOnboarded`, `LeaveRequested`, `LeaveApproved`, `LeaveRejected`, `LeaveCancelled`.
  - Stores exactly one notification per `event_id` for `payload.employee_id`.
  - Logs simulated email line: `SIMULATED EMAIL to employee <id>: <message>`.
- **Notification Messages**:
  - `EmployeeOnboarded`: `"Welcome <name>, your account is ready."`
  - Leave events (`LeaveRequested`, `LeaveApproved`, `LeaveRejected`, `LeaveCancelled`): `"Your <leave_type> leave from <start> to <end> (<days> days) was <requested|approved|rejected|cancelled>."`

---

## Gateway Payload Details

- **Routing by path prefix**:
  - `/auth` -> Auth service (`:8001`)
  - `/employees` -> Employee service (`:8002`)
  - `/leaves` -> Leave service (`:8003`)
  - `/payroll` and `/payslips` -> Payroll service (`:8004`)
  - `/notifications` -> Notification service (`:8005`)
  - Any other path -> HTTP 404 with project error format (`{"error": {"code": "NOT_FOUND", "message": "..."}}`).

- **Internal path blocking**:
  - Any path starting with `/internal` (any HTTP method) -> HTTP 404 with project error format (`{"error": {"code": "NOT_FOUND", "message": "..."}}`), never forwarded to upstreams.

- **Authentication & Permissions**:
  - **Public endpoints (no JWT required)**: `POST /auth/login`, `GET /health`, `GET /metrics` (the gateway's own).
  - **Protected endpoints**: Every other routed path requires a valid JWT Bearer token in the `Authorization` header, else returns HTTP 401 with project error format (`{"error": {"code": "UNAUTHORIZED", "message": "..."}}`).
  - Header forwarding: The `Authorization` header is forwarded unchanged to upstream services; downstream services still verify JWT claims themselves.

- **Correlation ID Tracking**:
  - `X-Correlation-ID` header is processed via `ems_common` correlation middleware. The same ID is sent to upstream services and returned in the HTTP response client header.

- **Rate Limiting**:
  - In-memory fixed window per client IP (`request.client.host`).
  - General limit: `RATE_LIMIT_REQUESTS` requests per `RATE_LIMIT_WINDOW_SECONDS`.
  - Stricter limit for `POST /auth/login`: `LOGIN_RATE_LIMIT_REQUESTS` requests per `RATE_LIMIT_WINDOW_SECONDS`.
  - Exceeded limit -> HTTP 429 with `Retry-After` header and project error format code `RATE_LIMITED`.
  - `/health` and `/metrics` are exempt from rate limiting.
  - Expired window entries are automatically cleaned up to prevent memory leaks. Counters are per gateway instance.

- **Upstream Failures**:
  - Upstream connection error -> HTTP 502 with error code `UPSTREAM_UNAVAILABLE`.
  - Upstream timeout -> HTTP 504 with error code `UPSTREAM_TIMEOUT`.
  - Upstream status codes, bodies, and relevant headers pass through unchanged otherwise.
  - The gateway **NEVER** retries requests (preventing duplicate resource creation).


