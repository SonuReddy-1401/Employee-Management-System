# Requirements Traceability Matrix

This document provides end-to-end traceability mapping each requirement from `docs/REQUIREMENTS.md` to automated test suites across all test pyramid levels.

## Traceability Matrix Table

| Requirement ID | Requirement Summary | Unit | Integration | Contract | E2E | Chaos | Load | UI | Total Tests |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **R-001** | `POST /auth/login` authenticates user credentials and returns JWT `access_token`. | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-002** | `POST /auth/login` returns 401 on invalid email or password with generic error message. | 0 | 2 | 1 | 0 | 0 | 0 | 0 | **3** |
| **R-003** | `POST /internal/users` creates user credentials with ID, email, password, and role. | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-004** | `POST /internal/users` returns 409 on duplicate ID/email and 422 on invalid role/short password. | 0 | 4 | 0 | 0 | 0 | 0 | 0 | **4** |
| **R-005** | `DELETE /internal/users/{id}` deletes user credentials and returns 204 idempotently. | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-006** | `POST /employees` initiates onboarding saga, creates employee, syncs Auth/Payroll, sets status `ACTIVE`. | 1 | 1 | 1 | 1 | 0 | 0 | 0 | **4** |
| **R-007** | `POST /employees` returns 502 `ONBOARDING_FAILED` and compensates completed steps when saga fails. | 1 | 2 | 0 | 0 | 2 | 0 | 1 | **6** |
| **R-008** | `POST /employees` returns 409 on duplicate email and 422 on invalid manager_id or payload. | 0 | 2 | 1 | 0 | 0 | 0 | 0 | **3** |
| **R-009** | `GET /employees` returns paginated list excluding soft-deleted employees, supporting department filter. | 1 | 1 | 0 | 0 | 0 | 0 | 0 | **2** |
| **R-010** | `GET /employees/{id}` returns single employee record or 404 if missing/soft-deleted. | 0 | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| **R-011** | `PUT /employees/{id}` updates employee fields; returns 404 if missing, 409 duplicate email, 422 self-manager. | 1 | 1 | 0 | 0 | 0 | 0 | 0 | **2** |
| **R-012** | `DELETE /employees/{id}` soft-deletes employee, sets `deleted_at`, and returns 204 idempotently. | 0 | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| **R-013** | `POST /leaves` creates `PENDING` leave request for Monday-Friday weekdays and writes `LeaveRequested` outbox event. | 1 | 1 | 1 | 0 | 0 | 0 | 0 | **3** |
| **R-014** | `POST /leaves` validates active employee via Employee service cached in Redis; returns 422 if missing/inactive, 503 if unreachable. | 0 | 5 | 0 | 0 | 1 | 0 | 0 | **6** |
| **R-015** | `POST /leaves` returns 409 if dates overlap existing leave, or 422 if paid leave exceeds annual allowance. | 2 | 2 | 0 | 0 | 0 | 0 | 0 | **4** |
| **R-016** | `POST /leaves/{id}/approve` transitions leave `PENDING` -> `APPROVED`, checks balance, writes `LeaveApproved` event, or returns 409/403. | 1 | 3 | 0 | 0 | 1 | 0 | 0 | **5** |
| **R-017** | `POST /leaves/{id}/reject` transitions leave `PENDING` -> `REJECTED` and writes `LeaveRejected` outbox event. | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-018** | `POST /leaves/{id}/cancel` transitions leave (`PENDING`/`APPROVED`) -> `CANCELLED`; writes `LeaveCancelled` event only for approved leave. | 0 | 3 | 1 | 1 | 0 | 0 | 0 | **5** |
| **R-019** | `GET /leaves` lists leave requests with role-based visibility (EMPLOYEE own, MANAGER team/own, HR/ADMIN all). | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-020** | `GET /leaves/balance/{employee_id}` calculates annual allowance, used days, and remaining balance for employee. | 0 | 1 | 1 | 0 | 0 | 0 | 1 | **3** |
| **R-021** | `POST /internal/profiles` creates payroll profile with salary idempotently (201 new, 200 duplicate same salary, 409 different salary). | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-022** | `DELETE /internal/profiles/{employee_id}` deletes payroll profile idempotently returning 204. | 0 | 1 | 1 | 0 | 0 | 0 | 0 | **2** |
| **R-023** | `POST /payroll/run` processes batch payroll for YYYY-MM by calculating unpaid leave deductions using Monday-Friday working days. | 1 | 0 | 2 | 0 | 0 | 0 | 0 | **3** |
| **R-024** | `GET /payslips/{employee_id}` retrieves payslips ordered by month descending; HR/ADMIN read any, others read own (403 otherwise). | 0 | 0 | 1 | 0 | 0 | 0 | 0 | **1** |
| **R-025** | Notification service consumes domain events, stores notifications idempotently per `event_id`, and logs simulated emails. | 1 | 2 | 1 | 0 | 1 | 0 | 0 | **5** |
| **R-026** | `GET /notifications/{employee_id}` lists notifications for an employee; HR/ADMIN read any, others read own (403 otherwise). | 0 | 2 | 0 | 0 | 0 | 0 | 1 | **3** |
| **R-027** | Outbox pattern writes event rows in same database transaction; background publisher delivers to exchange `ems.events`. | 1 | 3 | 0 | 0 | 0 | 0 | 0 | **4** |
| **R-028** | Consumers process events idempotently via `processed_events` table and route failed messages to Dead-Letter Queue (DLQ) after max retries. | 1 | 3 | 0 | 0 | 0 | 0 | 0 | **4** |
| **R-029** | API Gateway routes by path prefix (`/auth`, `/employees`, `/leaves`, `/payroll`, `/notifications`) and blocks `/internal/*` with 404. | 0 | 0 | 2 | 0 | 0 | 0 | 0 | **2** |
| **R-030** | API Gateway requires valid Bearer JWT for protected endpoints (401 if missing/invalid) and forwards Authorization header upstream. | 0 | 0 | 1 | 1 | 0 | 0 | 0 | **2** |
| **R-031** | API Gateway enforces IP rate limiting (100 req/min general, 10 req/min login), returning 429 `RATE_LIMITED`. | 0 | 0 | 0 | 0 | 0 | 1 | 0 | **1** |
| **R-032** | Header `X-Correlation-ID` is generated/propagated across all HTTP requests and async event envelopes. | 2 | 0 | 0 | 1 | 0 | 0 | 0 | **3** |
| **R-033** | Dashboard screen renders role-specific card layout within a budget of at most 6 API requests per page load. | 0 | 0 | 0 | 0 | 0 | 0 | 3 | **3** |
| **R-034** | Employees screen allows HR/ADMIN to onboard, edit, and soft-delete employees, while MANAGER has read-only access. | 0 | 0 | 0 | 0 | 0 | 0 | 1 | **1** |
| **R-035** | Leave screen allows requesting leaves with inline weekday date validation and manager decision controls. | 1 | 0 | 0 | 0 | 0 | 0 | 1 | **2** |
| **R-036** | Payroll screen allows HR/ADMIN to run batch payroll with confirmation dialog and view payslip breakdown modal. | 0 | 0 | 0 | 0 | 0 | 0 | 1 | **1** |
| **R-037** | System screen restricts access to HR/ADMIN and displays real-time health checks (`UP`/`DOWN`) and infrastructure telemetry links. | 0 | 0 | 0 | 0 | 0 | 0 | 1 | **1** |

## GAP Analysis

Zero GAPs identified. 100% of defined requirements have at least one automated test mapped across the test pyramid.


## Summary Metrics

- **Total Requirements Defined**: 37 [R-001 through R-037]
- **Total Mapped Requirements**: 37
- **Total GAP Requirements**: 0
- **Total Test Mappings**: 102
