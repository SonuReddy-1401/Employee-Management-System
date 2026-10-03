# System Facts Repository

This document serves as the single source of truth for all quantitative metrics, versions, configurations, test counts, coverage numbers, bug reports, and architectural specifications across the Employee Management System.

Collected on: `2026-10-03 15:11:35`

---

## Fact Table

| ID | Category | Fact | Value | Source | Collected on |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F-001** | `ARCH` | Container Count | 15 containers | `docker-compose.yml` | 2026-10-03 15:11:35 |
| **F-002** | `ARCH` | Frontend Container | Port 8080 (Published `8080:80`) | `docker-compose.yml:165` | 2026-10-03 15:11:35 |
| **F-003** | `ARCH` | Gateway Service | Port 8000 (Published `8000:8000`) | `docker-compose.yml:6` | 2026-10-03 15:11:35 |
| **F-004** | `ARCH` | Auth Service | Port 8001 (Published `8001:8001`) | `docker-compose.yml:33` | 2026-10-03 15:11:35 |
| **F-005** | `ARCH` | Auth Database | Port 5432 (Published `5432:5432`), DB `auth_db` | `docker-compose.yml:25` | 2026-10-03 15:11:35 |
| **F-006** | `ARCH` | Employee Service | Port 8002 (Published `8002:8002`) | `docker-compose.yml:58` | 2026-10-03 15:11:35 |
| **F-007** | `ARCH` | Employee Database | Port 5433 (Published `5433:5432`), DB `employee_db` | `docker-compose.yml:50` | 2026-10-03 15:11:35 |
| **F-008** | `ARCH` | Leave Service | Port 8003 (Published `8003:8003`) | `docker-compose.yml:84` | 2026-10-03 15:11:35 |
| **F-009** | `ARCH` | Leave Database | Port 5434 (Published `5434:5432`), DB `leave_db` | `docker-compose.yml:76` | 2026-10-03 15:11:35 |
| **F-010** | `ARCH` | Payroll Service | Port 8004 (Published `8004:8004`) | `docker-compose.yml:110` | 2026-10-03 15:11:35 |
| **F-011** | `ARCH` | Payroll Database | Port 5435 (Published `5435:5432`), DB `payroll_db` | `docker-compose.yml:102` | 2026-10-03 15:11:35 |
| **F-012** | `ARCH` | Notification Service | Port 8005 (Published `8005:8005`) | `docker-compose.yml:136` | 2026-10-03 15:11:35 |
| **F-013** | `ARCH` | Notification Database | Port 5436 (Published `5436:5432`), DB `notification_db` | `docker-compose.yml:128` | 2026-10-03 15:11:35 |
| **F-014** | `ARCH` | RabbitMQ Broker | Ports 5672, 15672 (Published `5672:5672`, `15672:15672`) | `docker-compose.yml:148` | 2026-10-03 15:11:35 |
| **F-015** | `ARCH` | Redis Cache | Port 6379 (Published `6379:6379`) | `docker-compose.yml:158` | 2026-10-03 15:11:35 |
| **F-016** | `ARCH` | Prometheus Telemetry | Port 9090 (Published `9090:9090`) | `docker-compose.yml:174` | 2026-10-03 15:11:35 |
| **F-017** | `STACK` | Python Runtime | Pinned version 3.12-slim | `Dockerfile:1` | 2026-10-03 15:11:35 |
| **F-018** | `STACK` | FastAPI Framework | Pinned version 0.115.0 | `requirements.txt:1` | 2026-10-03 15:11:35 |
| **F-019** | `STACK` | SQLAlchemy ORM | Pinned version 2.0.35 | `requirements.txt:3` | 2026-10-03 15:11:35 |
| **F-020** | `STACK` | PostgreSQL Image | Pinned tag postgres:16-alpine | `docker-compose.yml:26` | 2026-10-03 15:11:35 |
| **F-021** | `STACK` | RabbitMQ Image | Pinned tag rabbitmq:3.13-management-alpine | `docker-compose.yml:149` | 2026-10-03 15:11:35 |
| **F-022** | `STACK` | Redis Image | Pinned tag redis:7-alpine | `docker-compose.yml:159` | 2026-10-03 15:11:35 |
| **F-023** | `STACK` | React Frontend | Pinned version 18.3.1 | `frontend/package.json:15` | 2026-10-03 15:11:35 |
| **F-024** | `STACK` | Vite Build Tool | Pinned version 6.4.3 | `frontend/package.json:23` | 2026-10-03 15:11:35 |
| **F-025** | `STACK` | Vitest Test Runner | Pinned version 2.1.9 | `frontend/package.json:24` | 2026-10-03 15:11:35 |
| **F-026** | `STACK` | pytest Test Runner | Pinned version 8.3.3 | `requirements-dev.txt:1` | 2026-10-03 15:11:35 |
| **F-027** | `STACK` | k6 Load Runner | Pinned tag grafana/k6:2.3.0 | `docker-compose.load.yml:6` | 2026-10-03 15:11:35 |
| **F-028** | `API` | Auth Service Endpoints | 3 endpoints (`/auth/login`, `/internal/users`, `/internal/users/{id}`) | `docs/CONTRACTS.md:28` | 2026-10-03 15:11:35 |
| **F-029** | `API` | Employee Service Endpoints | 5 endpoints (`/employees`, `/employees/{id}`, etc.) | `docs/CONTRACTS.md:41` | 2026-10-03 15:11:35 |
| **F-030** | `API` | Leave Service Endpoints | 6 endpoints (`/leaves`, `/leaves/{id}/approve`, `/leaves/balance/{id}`, etc.) | `docs/CONTRACTS.md:66` | 2026-10-03 15:11:35 |
| **F-031** | `API` | Payroll Service Endpoints | 4 endpoints (`/internal/profiles`, `/payroll/run`, `/payslips/{id}`, etc.) | `docs/CONTRACTS.md:89` | 2026-10-03 15:11:35 |
| **F-032** | `API` | Notification Service Endpoints | 1 endpoint (`/notifications/{employee_id}`) | `docs/CONTRACTS.md:106` | 2026-10-03 15:11:35 |
| **F-033** | `API` | RabbitMQ Topic Exchange | Exchange name `ems.events` | `docs/CONTRACTS.md:145` | 2026-10-03 15:11:35 |
| **F-034** | `API` | Event Types | 5 types (`EmployeeOnboarded`, `LeaveRequested`, `LeaveApproved`, `LeaveRejected`, `LeaveCancelled`) | `docs/CONTRACTS.md:152` | 2026-10-03 15:11:35 |
| **F-035** | `TESTS` | `libs/common` Unit Tests | 27 tests collected | `pytest libs/common --collect-only` | 2026-10-03 15:11:35 |
| **F-036** | `TESTS` | `services/auth` Unit Tests | 13 tests collected | `pytest services/auth --collect-only` | 2026-10-03 15:11:35 |
| **F-037** | `TESTS` | `services/employee` Unit Tests | 29 tests collected | `pytest services/employee --collect-only` | 2026-10-03 15:11:35 |
| **F-038** | `TESTS` | `services/leave` Unit Tests | 29 tests collected | `pytest services/leave --collect-only` | 2026-10-03 15:11:35 |
| **F-039** | `TESTS` | `services/payroll` Unit Tests | 23 tests collected | `pytest services/payroll --collect-only` | 2026-10-03 15:11:35 |
| **F-040** | `TESTS` | `services/notification` Unit Tests | 12 tests collected | `pytest services/notification --collect-only` | 2026-10-03 15:11:35 |
| **F-041** | `TESTS` | `tests/contract` Test Suite | 31 tests collected | `pytest tests/contract --collect-only` | 2026-10-03 15:11:35 |
| **F-042** | `TESTS` | `tests/e2e` Test Suite | 7 tests collected | `pytest tests/e2e --collect-only` | 2026-10-03 15:11:35 |
| **F-043** | `TESTS` | `tests/chaos` Test Suite | 6 tests collected | `pytest tests/chaos --collect-only` | 2026-10-03 15:11:35 |
| **F-044** | `TESTS` | `tests/load` Test Suite | 3 tests collected | `pytest tests/load --collect-only` | 2026-10-03 15:11:35 |
| **F-045** | `TESTS` | Frontend Vitest Test Suite | 99 unit tests across 17 test files | `cd frontend; npm test -- --run` | 2026-10-03 15:11:35 |
| **F-046** | `TESTS` | Playwright E2E Test Count | 0 tests (frontend/e2e directory does not exist) | Directory check `frontend/e2e` | 2026-10-03 15:11:35 |
| **F-047** | `COVERAGE` | `libs/common` Coverage | Overall 89.8%, Domain N/A, Passed 24, Failed 0 | `docs/COVERAGE.md:5` | 2026-10-03 15:11:35 |
| **F-048** | `COVERAGE` | `services/auth` Coverage | Overall 82.5%, Domain 100.0%, Passed 13, Failed 0 | `docs/COVERAGE.md:6` | 2026-10-03 15:11:35 |
| **F-049** | `COVERAGE` | `services/employee` Coverage | Overall 82.8%, Domain 100.0%, Passed 28, Failed 0 | `docs/COVERAGE.md:7` | 2026-10-03 15:11:35 |
| **F-050** | `COVERAGE` | `services/leave` Coverage | Overall 76.6%, Domain 98.1%, Passed 29, Failed 0 | `docs/COVERAGE.md:8` | 2026-10-03 15:11:35 |
| **F-051** | `COVERAGE` | `services/payroll` Coverage | Overall 85.8%, Domain 98.5%, Passed 23, Failed 0 | `docs/COVERAGE.md:9` | 2026-10-03 15:11:35 |
| **F-052** | `COVERAGE` | `services/notification` Coverage | Overall 81.7%, Domain 100.0%, Passed 12, Failed 0 | `docs/COVERAGE.md:10` | 2026-10-03 15:11:35 |
| **F-053** | `COVERAGE` | `services/gateway` Coverage | Overall 96.2%, Domain 100.0%, Passed 18, Failed 0 | `docs/COVERAGE.md:11` | 2026-10-03 15:11:35 |
| **F-054** | `LOAD` | k6 Scenario `reads` p(95) | 25.92 ms (Avg 13.83 ms, p(90) 20.19 ms, Max 195.74 ms, 1,729 iterations, 0.00% failure) | `docs/LOAD_RESULTS.md:21` | 2026-10-03 15:11:35 |
| **F-055** | `LOAD` | k6 Scenario `create_leave` p(95) | 204.55 ms (Avg 75.64 ms, p(90) 165.09 ms, Max 470.63 ms, 4,940 iterations, 0.00% failure) | `docs/LOAD_RESULTS.md:22` | 2026-10-03 15:11:35 |
| **F-056** | `LOAD` | k6 Scenario `approve_leave` p(95) | 153.79 ms (Avg 52.12 ms, p(90) 112.59 ms, Max 336.02 ms, 4,940 iterations, 0.00% failure) | `docs/LOAD_RESULTS.md:23` | 2026-10-03 15:11:35 |
| **F-057** | `LOAD` | k6 Scenario `onboarding` p(95) | 296.90 ms (Avg 269.40 ms, p(90) 287.13 ms, Max 323.21 ms, 120 iterations, 0.00% failure) | `docs/LOAD_RESULTS.md:25` | 2026-10-03 15:11:35 |
| **F-058** | `LOAD` | k6 Overall Checks Pass Rate | 100.00% (28,398 checks passed out of 28,398) | `docs/LOAD_RESULTS.md:26` | 2026-10-03 15:11:35 |
| **F-059** | `LOAD` | DB Convergence Duration | 3.37 seconds for all table count deltas to converge post-load | `docs/LOAD_RESULTS.md:52` | 2026-10-03 15:11:35 |
| **F-060** | `CHAOS` | Chaos S1 Payroll Down Recovery | Recovery time 0.43s (Saga returns 502 `ONBOARDING_FAILED`, Auth compensated) | `docs/CHAOS_RESULTS.md:9` | 2026-10-03 15:11:35 |
| **F-061** | `CHAOS` | Chaos S2 Auth Down Recovery | Recovery time 0.43s (Saga returns 502 `ONBOARDING_FAILED`, zero orphaned records) | `docs/CHAOS_RESULTS.md:10` | 2026-10-03 15:11:35 |
| **F-062** | `CHAOS` | Chaos S3 RabbitMQ Outage Recovery | Recovery time 6.13s (Leave approved 200 OK, outbox buffered and published post-recovery) | `docs/CHAOS_RESULTS.md:11` | 2026-10-03 15:11:35 |
| **F-063** | `CHAOS` | Chaos S4 Notification Outage Recovery | Recovery time 0.18s (Events buffered in RabbitMQ, delivered post-recovery with zero duplicates) | `docs/CHAOS_RESULTS.md:12` | 2026-10-03 15:11:35 |
| **F-064** | `CHAOS` | Chaos S5 Redis Outage Fallback | Recovery time N/A (Direct HTTP fallback to Employee service succeeded synchronously) | `docs/CHAOS_RESULTS.md:13` | 2026-10-03 15:11:35 |
| **F-065** | `CHAOS` | Chaos S6 Prometheus Telemetry | Prometheus query `increase(http_requests_total{status=~"5..", job="employee"}[30m])` returned 4.04 | `docs/CHAOS_RESULTS.md:14` | 2026-10-03 15:11:35 |
| **F-066** | `BUGS` | Recorded System Bugs | 4 entries in `docs/BUG_REPORTS.md` (BUG-001, BUG-002, BUG-003, BUG-004) | `docs/BUG_REPORTS.md:1` | 2026-10-03 15:11:35 |
| **F-067** | `CI` | GitHub Actions Pipeline URL | `https://github.com/SonuReddy-1401/Employee-Management-System/actions/runs/37105655550` | `docs/STUDENT_INPUTS.md:112` | 2026-10-03 15:11:35 |
| **F-068** | `UI` | Frontend Supported Roles | 4 roles (`ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`) | `frontend/src/lib/permissions.js:1` | 2026-10-03 15:11:35 |
| **F-069** | `REPO` | Total Git Commits | 32 commits | `git rev-list --count HEAD` | 2026-10-03 15:11:35 |
| **F-070** | `REPO` | Code Base Statistics | 295 files, 24,139 total lines of code | `git ls-files` analysis script | 2026-10-03 15:11:35 |

---

## Concept Map

| Concept | Code Location (File & Line) | Test Proving It |
| :--- | :--- | :--- |
| Service decomposition | `services/employee/app/main.py:1` | `services/employee/tests/integration/test_employee_api.py:30` |
| Database per service | `docker-compose.yml:25` | `services/employee/tests/integration/test_employee_api.py:16` |
| API gateway | `services/gateway/app/main.py:1` | `tests/contract/test_gateway_contract.py:10` |
| Service discovery via Docker DNS | `docker-compose.yml:10` | `tests/e2e/test_e2e_scenarios.py:40` |
| Synchronous REST | `services/employee/app/api/routes.py:40` | `services/employee/tests/integration/test_employee_api.py:30` |
| Asynchronous messaging with a topic exchange | `libs/common/ems_common/consumer.py:10` | `libs/common/tests/integration/test_broker.py:10` |
| Transactional outbox | `libs/common/ems_common/outbox.py:10` | `libs/common/tests/integration/test_broker.py:10` |
| Idempotent consumer | `libs/common/ems_common/consumer.py:25` | `libs/common/tests/integration/test_broker.py:25` |
| Dead-letter queue | `libs/common/ems_common/consumer.py:40` | `libs/common/tests/integration/test_broker.py:40` |
| Retry with backoff | `libs/common/ems_common/http_client.py:20` | `libs/common/tests/test_http_client.py:10` |
| Circuit breaker | `libs/common/ems_common/http_client.py:45` | `libs/common/tests/test_http_client.py:35` |
| Saga with compensation | `services/employee/app/domain/saga.py:15` | `services/employee/tests/integration/test_employee_api.py:55` |
| Eventual consistency | `services/payroll/app/consumer_handler.py:20` | `tests/e2e/test_e2e_scenarios.py:25` |
| Caching with fallback | `services/leave/app/clients/employee_client.py:25` | `services/leave/tests/integration/test_leave_api.py:50` |
| Rate limiting | `services/gateway/app/main.py:35` | `tests/contract/test_gateway_contract.py:20` |
| Correlation-ID tracing | `libs/common/ems_common/correlation.py:10` | `libs/common/tests/test_correlation.py:5` |
| Health checks | `services/employee/app/main.py:20` | `services/employee/tests/integration/test_employee_api.py:10` |
| Metrics and dashboards | `services/employee/app/main.py:25` | `tests/chaos/test_zz_prometheus.py:5` |
| Fault injection | `tests/chaos/test_01_onboarding_payroll_chaos.py:10` | `tests/chaos/test_01_onboarding_payroll_chaos.py:15` |

### Not Claimed
- Transactional outbox with CDC / Debezium (application poll-and-publish loop used instead of database log scraping CDC)
