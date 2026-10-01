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
| `POST` | `/employees` | Triggers Onboarding Saga |
| `GET` | `/employees` | List all employees |
| `PUT` | `/employees/{id}` | Update employee record by ID |
| `GET` | `/employees/{id}` | Get employee by ID |
| `DELETE` | `/employees/{id}` | Soft delete employee |

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

---

## Cross-Cutting Concerns

- **Header Propagation**: Header `X-Correlation-ID` is generated at the Gateway and propagated in all HTTP calls and async events.
- **Health & Metrics**: `/health` and `/metrics` implemented on every service.
- **Resilience**: Synchronous service calls use timeout + `tenacity` retry + `pybreaker` circuit breaker.
