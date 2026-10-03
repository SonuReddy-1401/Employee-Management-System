# System Requirements Specification

This document defines all testable functional, non-functional, security, and interface requirements derived strictly from `docs/CONTRACTS.md` and `docs/UI.md`.

---

## Requirements Table

| ID | Requirement Text (Short) | Source (File & Section) |
| :--- | :--- | :--- |
| **R-001** | `POST /auth/login` authenticates user credentials and returns JWT `access_token`. | `docs/CONTRACTS.md:28` (Auth Service) |
| **R-002** | `POST /auth/login` returns 401 on invalid email or password with generic error message. | `docs/CONTRACTS.md:36` (Auth Service) |
| **R-003** | `POST /internal/users` creates user credentials with ID, email, password, and role. | `docs/CONTRACTS.md:37` (Auth Service) |
| **R-004** | `POST /internal/users` returns 409 on duplicate ID/email and 422 on invalid role/short password. | `docs/CONTRACTS.md:37` (Auth Service) |
| **R-005** | `DELETE /internal/users/{id}` deletes user credentials and returns 204 idempotently. | `docs/CONTRACTS.md:38` (Auth Service) |
| **R-006** | `POST /employees` initiates onboarding saga, creates employee, syncs Auth/Payroll, sets status `ACTIVE`. | `docs/CONTRACTS.md:52` (Employee Service) |
| **R-007** | `POST /employees` returns 502 `ONBOARDING_FAILED` and compensates completed steps when saga fails. | `docs/CONTRACTS.md:52` (Employee Service) |
| **R-008** | `POST /employees` returns 409 on duplicate email and 422 on invalid manager_id or payload. | `docs/CONTRACTS.md:52` (Employee Service) |
| **R-009** | `GET /employees` returns paginated list excluding soft-deleted employees, supporting department filter. | `docs/CONTRACTS.md:54` (Employee Service) |
| **R-010** | `GET /employees/{id}` returns single employee record or 404 if missing/soft-deleted. | `docs/CONTRACTS.md:55` (Employee Service) |
| **R-011** | `PUT /employees/{id}` updates employee fields; returns 404 if missing, 409 duplicate email, 422 self-manager. | `docs/CONTRACTS.md:56` (Employee Service) |
| **R-012** | `DELETE /employees/{id}` soft-deletes employee, sets `deleted_at`, and returns 204 idempotently. | `docs/CONTRACTS.md:57` (Employee Service) |
| **R-013** | `POST /leaves` creates `PENDING` leave request for Monday-Friday weekdays and writes `LeaveRequested` outbox event. | `docs/CONTRACTS.md:77` (Leave Service) |
| **R-014** | `POST /leaves` validates active employee via Employee service cached in Redis; returns 422 if missing/inactive, 503 if unreachable. | `docs/CONTRACTS.md:80` (Leave Service) |
| **R-015** | `POST /leaves` returns 409 if dates overlap existing leave, or 422 if paid leave exceeds annual allowance. | `docs/CONTRACTS.md:81` (Leave Service) |
| **R-016** | `POST /leaves/{id}/approve` transitions leave `PENDING` -> `APPROVED`, checks balance, writes `LeaveApproved` event, or returns 409/403. | `docs/CONTRACTS.md:83` (Leave Service) |
| **R-017** | `POST /leaves/{id}/reject` transitions leave `PENDING` -> `REJECTED` and writes `LeaveRejected` outbox event. | `docs/CONTRACTS.md:83` (Leave Service) |
| **R-018** | `POST /leaves/{id}/cancel` transitions leave (`PENDING`/`APPROVED`) -> `CANCELLED`; writes `LeaveCancelled` event only for approved leave. | `docs/CONTRACTS.md:84` (Leave Service) |
| **R-019** | `GET /leaves` lists leave requests with role-based visibility (EMPLOYEE own, MANAGER team/own, HR/ADMIN all). | `docs/CONTRACTS.md:85` (Leave Service) |
| **R-020** | `GET /leaves/balance/{employee_id}` calculates annual allowance, used days, and remaining balance for employee. | `docs/CONTRACTS.md:86` (Leave Service) |
| **R-021** | `POST /internal/profiles` creates payroll profile with salary idempotently (201 new, 200 duplicate same salary, 409 different salary). | `docs/CONTRACTS.md:98` (Payroll Service) |
| **R-022** | `DELETE /internal/profiles/{employee_id}` deletes payroll profile idempotently returning 204. | `docs/CONTRACTS.md:99` (Payroll Service) |
| **R-023** | `POST /payroll/run` processes batch payroll for YYYY-MM by calculating unpaid leave deductions using Monday-Friday working days. | `docs/CONTRACTS.md:101` (Payroll Service) |
| **R-024** | `GET /payslips/{employee_id}` retrieves payslips ordered by month descending; HR/ADMIN read any, others read own (403 otherwise). | `docs/CONTRACTS.md:103` (Payroll Service) |
| **R-025** | Notification service consumes domain events, stores notifications idempotently per `event_id`, and logs simulated emails. | `docs/CONTRACTS.md:194` (Notification Service) |
| **R-026** | `GET /notifications/{employee_id}` lists notifications for an employee; HR/ADMIN read any, others read own (403 otherwise). | `docs/CONTRACTS.md:189` (Notification Service) |
| **R-027** | Outbox pattern writes event rows in same database transaction; background publisher delivers to exchange `ems.events`. | `docs/CONTRACTS.md:158` (Events & Messaging) |
| **R-028** | Consumers process events idempotently via `processed_events` table and route failed messages to Dead-Letter Queue (DLQ) after max retries. | `docs/CONTRACTS.md:178` (Events & Messaging) |
| **R-029** | API Gateway routes by path prefix (`/auth`, `/employees`, `/leaves`, `/payroll`, `/notifications`) and blocks `/internal/*` with 404. | `docs/CONTRACTS.md:206` (Gateway Payload Details) |
| **R-030** | API Gateway requires valid Bearer JWT for protected endpoints (401 if missing/invalid) and forwards Authorization header upstream. | `docs/CONTRACTS.md:217` (Gateway Payload Details) |
| **R-031** | API Gateway enforces IP rate limiting (100 req/min general, 10 req/min login), returning 429 `RATE_LIMITED`. | `docs/CONTRACTS.md:225` (Gateway Payload Details) |
| **R-032** | Header `X-Correlation-ID` is generated/propagated across all HTTP requests and async event envelopes. | `docs/CONTRACTS.md:169` (Cross-Cutting Concerns) |
| **R-033** | Dashboard screen renders role-specific card layout within a budget of at most 6 API requests per page load. | `docs/UI.md:106` (Dashboard Screen) |
| **R-034** | Employees screen allows HR/ADMIN to onboard, edit, and soft-delete employees, while MANAGER has read-only access. | `docs/UI.md:114` (Employees Screen) |
| **R-035** | Leave screen allows requesting leaves with inline weekday date validation and manager decision controls. | `docs/UI.md:120` (Leave Management Screen) |
| **R-036** | Payroll screen allows HR/ADMIN to run batch payroll with confirmation dialog and view payslip breakdown modal. | `docs/UI.md:125` (Payroll & Payslips Screen) |
| **R-037** | System screen restricts access to HR/ADMIN and displays real-time health checks (`UP`/`DOWN`) and infrastructure telemetry links. | `docs/UI.md:141` (System Health Screen) |
