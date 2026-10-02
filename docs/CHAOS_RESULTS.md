# Chaos Test Execution Results

This document records the empirical results and observations from running the EMS Chaos Test Suite (`tests/chaos/`). All tests were executed against the live Docker Compose microservice environment.

## Scenario Summary & Results

| Scenario ID | Test Name | Target Component Outage | Expected Behavior | Observed Behavior | Measured Recovery Time | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S1** | `test_payroll_down_during_onboarding` | `payroll` (HTTP 8004) | Saga returns 502 `ONBOARDING_FAILED`; employee status set to `ONBOARDING_FAILED`; Auth compensated (login returns 401); no `EmployeeOnboarded` event published; Gateway returns 502 `UPSTREAM_UNAVAILABLE` on payslip query. Recovery polling succeeds after service start. | All assertions met exactly as expected. HTTP 502 with `ONBOARDING_FAILED` code returned, auth user deleted during saga rollback, no event published, and Gateway upstream failure returned. Onboarding recovered instantly once service started. | **0.43 seconds** | **PASS** |
| **S2** | `test_auth_down_during_onboarding` | `auth` (HTTP 8001) | Saga returns 502 `ONBOARDING_FAILED`; employee status set to `ONBOARDING_FAILED`; no orphaned payroll profile created when payroll run executes post-recovery. Recovery polling succeeds after service start. | All assertions met. HTTP 502 returned, department search confirms `ONBOARDING_FAILED`, payroll run created zero payslips for failed employee ID. Recovery onboarding succeeded post-restart. | **0.43 seconds** | **PASS** |
| **S3** | `test_rabbitmq_down_during_leave_approval` | `rabbitmq` (AMQP 5672) | Manager approve leave succeeds with 200 OK (outbox table buffers event); event published once RabbitMQ recovers; Notification service receives `LeaveApproved` event; Payroll run includes unpaid leave deduction. | Leave approved synchronously (200 OK). Outbox publisher background loop retried safely during RabbitMQ outage and published buffered event once AMQP connection was re-established. Notification delivered and Payroll calculated 5 unpaid leave days deduction. | **6.13 seconds** | **PASS** |
| **S4** | `test_notification_down_event_durability` | `notification` (HTTP 8005) | Onboarding and leave creation succeed; events buffered in durable RabbitMQ queues; notifications delivered without loss or duplication after Notification service recovers. | Both `EmployeeOnboarded` and `LeaveRequested` events were consumed upon Notification service restart. Exactly one notification for each event was delivered with zero duplicates. | **0.18 seconds** | **PASS** |
| **S5** | `test_redis_down_leave_creation` | `redis` (TCP 6379) | Leave creation and leave balance queries succeed via fallback to Employee service direct HTTP call; second leave succeeds after Redis recovers. | Leave creation (HTTP 201) and balance retrieval (HTTP 200) completed successfully during Redis outage via direct HTTP fallback. Post-recovery leave creation succeeded. | **N/A** (Synchronous Fallback) | **PASS** |
| **S6** | `test_prometheus_shows_5xx_after_chaos` | Prometheus Metrics | Prometheus records HTTP 5xx error rate increase for job `employee` over the past 30 minutes following chaos scenarios S1/S2. | Prometheus metric query `increase(http_requests_total{status=~"5..", job="employee"}[30m])` returned an observed increase of **4.04** HTTP 5xx errors for `employee`. | **N/A** (Observed Metric Increase: **4.04**) | **PASS** |

---

## Findings & System Resilience Observations

1. **Transactional Outbox Resilience (S3)**:
   - When RabbitMQ was abruptly stopped during leave approval, the Leave service saved the `APPROVED` state to PostgreSQL and inserted the event envelope into the `outbox` table within the same database transaction.
   - The outbox publisher logged AMQP connection errors (`[Errno -5] No address associated with hostname`) without failing HTTP requests.
   - Upon RabbitMQ restart, the outbox publisher automatically re-established its AMQP connection and published the pending `LeaveApproved` event within **6.13 seconds**, maintaining event durability and downstream consistency.

2. **Saga Compensation Integrity (S1 & S2)**:
   - When downstream microservices (`payroll` or `auth`) were unavailable during employee onboarding, the Employee saga initiated reverse compensation.
   - For `payroll` outage (S1), created Auth credentials were deleted via compensation HTTP call, ensuring no orphaned login credentials remained.
   - For `auth` outage (S2), the saga failed early before creating a payroll profile, ensuring no orphaned payroll entries existed.

3. **Redis Cache Fallback (S5)**:
   - The Leave service gracefully fell back to direct HTTP communication with the Employee service when Redis was unreachable. Leave creation and balance calculations functioned normally without throwing 500 errors.

4. **Observability Verification (S6)**:
   - Prometheus accurately scraped and recorded the 5xx responses emitted during S1/S2 onboarding failures under job `employee`, validating system telemetry end-to-end.
