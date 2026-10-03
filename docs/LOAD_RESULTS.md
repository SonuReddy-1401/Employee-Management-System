# Load Testing Execution Results

This document records the empirical results and performance metrics from running the EMS Load Testing Suite (`tests/load/ems.js` via `scripts/load.py`).

## Test Environment & Setup

- **Host Environment**: Windows Desktop running 15 Docker microservice containers via Docker Compose.
- **k6 Version**: `grafana/k6:2.3.0` (pinned via container runner).
- **Gateway Rate Limits**: Overridden during load execution via `docker-compose.load.yml` (`RATE_LIMIT_REQUESTS=1000000`, `LOGIN_RATE_LIMIT_REQUESTS=1000000`) and restored to development defaults (`RATE_LIMIT_REQUESTS=100`, `LOGIN_RATE_LIMIT_REQUESTS=10`) post-test.
- **Test Scenarios**:
  - `reads`: Ramping VUs (up to 30 VUs, duration 2m0s). High-frequency employee listing and detail queries.
  - `leave_flow`: Ramping VUs (up to 15 VUs, duration 1m50s, startTime 2m10s). Full end-to-end leave lifecycle: creation (`POST /leaves`), approval (`POST /leaves/{id}/approve`), and balance check (`GET /leaves/balance/{id}`).
  - `onboarding`: Constant arrival rate (2.00 iterations/sec for 60s, startTime 3m45s). Full distributed employee onboarding saga across Employee, Auth, and Payroll services.

---

## Scenario Performance & Threshold Results

| Scenario Name | Tagged Request / Metric | Total Requests / Iterations | Avg Latency | p(90) Latency | p(95) Latency | Max Latency | Failure Rate | Target Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **reads** | `GET /employees` & `GET /employees/{id}` | 1,729 iterations | 13.83 ms | 20.19 ms | 25.92 ms | 195.74 ms | 0.00% | `p(95) < 500ms`, `fail < 1%` | **PASS** |
| **leave_flow** | `create_leave` (`POST /leaves`) | 4,940 iterations | 75.64 ms | 165.09 ms | 204.55 ms | 470.63 ms | 0.00% | `p(95) < 1000ms` | **PASS** |
| **leave_flow** | `approve_leave` (`POST /leaves/{id}/approve`) | 4,940 iterations | 52.12 ms | 112.59 ms | 153.79 ms | 336.02 ms | 0.00% | `p(95) < 1000ms` | **PASS** |
| **leave_flow** | `balance` (`GET /leaves/balance/{id}`) | 4,940 iterations | not measured | not measured | not measured | not measured | 0.00% | `fail < 1%` | **PASS** |
| **onboarding** | `onboard_employee` (`POST /employees`) | 120 iterations | 269.40 ms | 287.13 ms | 296.90 ms | 323.21 ms | 0.00% | `p(95) < 3000ms`, `fail < 1%` | **PASS** |
| **Overall** | `checks` | 28,398 checks | N/A | N/A | N/A | N/A | 0.00% | `rate > 99%` | **PASS** (100.00%) |

> **Scenario Schedule & Overlap Note**: The onboarding scenario (startTime 3m45s) overlapped the end of the `leave_flow` scenario (which runs until roughly 4m00s) by approximately 15 seconds. Consequently, onboarding latency was measured while some concurrent leave traffic was still active. Note that all scenario start times and stage durations were specified by the test author, not by the agent.

### Threshold Results Summary

| Target Metric & Threshold | Measured Value | Threshold Target | Status |
| :--- | :--- | :--- | :--- |
| `http_req_duration{scenario:reads}` | p(95) = 25.92 ms | `p(95) < 500ms` | **PASS** |
| `http_req_failed{scenario:reads}` | rate = 0.00% | `rate < 0.01` | **PASS** |
| `http_req_duration{name:create_leave}` | p(95) = 204.55 ms | `p(95) < 1000ms` | **PASS** |
| `http_req_duration{name:approve_leave}` | p(95) = 153.79 ms | `p(95) < 1000ms` | **PASS** |
| `http_req_failed{scenario:leave_flow}` | rate = 0.00% | `rate < 0.01` | **PASS** |
| `http_req_duration{name:onboard_employee}` | p(95) = 296.90 ms | `p(95) < 3000ms` | **PASS** |
| `http_req_failed{scenario:onboarding}` | rate = 0.00% | `rate < 0.01` | **PASS** |
| `checks` | rate = 100.00% | `rate > 0.99` | **PASS** |

---

## Post-Run Queue & Database Row Count Verification

### Verification Methodology
Prior to executing k6, `scripts/load.py` records a baseline count of records across all database tables (`leaves`, `outbox`, `employees`, `users`, `payroll_profiles`, `leave_deductions`, `notifications`). After k6 completes and message queues drain, actual record count deltas (`current - baseline`) are polled every 2 seconds for up to 180 seconds until they match the expected deltas computed by `scripts/load_verify.py` from k6 summary check pass counts (including setup employees). Pure verification functions in `scripts/load_verify.py` are unit tested in `tests/load/test_load_verify.py` against exact matches, record losses, and duplicate records.

### Measured Database Delta Results

| Check Name | Target Table / Event | Expected Delta | Measured Actual Delta | Seconds until all count checks converged (measured once for the whole group) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `leaves_approved` | `leaves` (`status = APPROVED`) | 4,940 | 4,940 | 3.37s | **PASS** |
| `outbox_LeaveRequested` | `outbox` (`event_type = LeaveRequested`) | 4,940 | 4,940 | 3.37s | **PASS** |
| `outbox_LeaveApproved` | `outbox` (`event_type = LeaveApproved`) | 4,940 | 4,940 | 3.37s | **PASS** |
| `outbox_EmployeeOnboarded` | `outbox` (`event_type = EmployeeOnboarded`) | 135 | 135 | 3.37s | **PASS** |
| `employees_active` | `employees` (`status = ACTIVE`) | 135 | 135 | 3.37s | **PASS** |
| `auth_users` | `users` | 135 | 135 | 3.37s | **PASS** |
| `payroll_profiles` | `payroll_profiles` | 135 | 135 | 3.37s | **PASS** |
| `payroll_leave_deductions` | `leave_deductions` | 4,940 | 4,940 | 3.37s | **PASS** |
| `notifications_LeaveRequested` | `notifications` (`LeaveRequested`) | 4,940 | 4,940 | 3.37s | **PASS** |
| `notifications_LeaveApproved` | `notifications` (`LeaveApproved`) | 4,940 | 4,940 | 3.37s | **PASS** |
| `notifications_EmployeeOnboarded` | `notifications` (`EmployeeOnboarded`) | 135 | 135 | 3.37s | **PASS** |
| `notifications_no_duplicates` | `notifications` (`total == distinct(event_id)`) | 10,015 | 10,015 | 0.00s | **PASS** |
| `employees_non_active_unchanged` | `employees` (`status != ACTIVE`) | 0 | 0 | 0.00s | **PASS** |

---

## Findings & System Limitations

1. **Transactional Outbox & Event Generation Breakdown**:
   - The `leave_flow` scenario completed 4,940 iterations. Each iteration executed one leave creation and one leave approval, generating **4,940 `LeaveRequested` events** and **4,940 `LeaveApproved` events** (a total of **9,880 leave domain events**).
   - The setup phase onboarded **15 setup employees**, and the onboarding scenario onboarded **120 employees**, generating **135 `EmployeeOnboarded` events** total across outbox, auth, employee, payroll, and notification services.
   - All 10,015 events were written to PostgreSQL outbox tables, published to RabbitMQ, and verified in downstream database tables with zero duplicate records and zero missing records.
2. **Onboarding Saga Latency**:
   - Cross-service employee onboarding (involving Employee, Auth, and Payroll synchronous HTTP calls plus RabbitMQ outbox publish) averaged **269.40 ms** per onboarding request with a p(95) of **296.90 ms**, well under the 3,000 ms test threshold chosen by the author.
3. **Hardware Limitations**:
   - Test execution ran on a single development workstation hosting all 15 microservices, databases, Redis, RabbitMQ, Prometheus, and Grafana simultaneously.
