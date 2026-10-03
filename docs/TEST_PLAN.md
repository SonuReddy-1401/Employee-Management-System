# Master Test Plan & Quality Specification

## 1. Objectives

The Master Test Plan defines the test strategy, quality gates, environment specifications, defect management procedures, and automated test execution policies for the Employee Management System (EMS) [F-001]. The objective is to verify functional correctness, data consistency, security enforcement, fault tolerance, and load resilience across all microservices and frontend components.

---

## 2. Scope and out-of-scope

### 2.1 In-Scope
- Backend unit and domain logic testing across Python 3.12 microservices [F-017], [F-018].
- Service-level integration testing against PostgreSQL containers using Testcontainers [F-005]–[F-013].
- OpenAPI and AMQP contract testing across microservice boundaries [F-041].
- End-to-end multi-service transactional flow validation [F-042].
- Fault injection and chaos resilience testing (RabbitMQ outage, Redis crash, microservice downtime) [F-060]–[F-065].
- High-concurrency load testing using k6 [F-027], [F-054]–[F-058].
- Frontend UI component and permission matrix unit testing with Vitest [F-025], [F-045], [F-068].

### 2.2 Out-of-Scope (Explicitly Not Tested)
- Desktop or mobile web browsers other than Chromium.
- Multi-node Kubernetes production cluster deployments (testing is restricted to Docker Compose topology) [F-001].
- Multi-day soak or endurance load testing (load tests run for 10–30 minutes) [F-054]–[F-058].
- Formal penetration testing or automated dynamic application security testing (DAST) scanners.
- Native mobile applications (iOS/Android).

---

## 3. Test pyramid & test level catalogue

The test strategy follows a classic Test Pyramid model, balancing fast isolated unit tests at the base with targeted end-to-end and chaos tests at the apex [F-035]–[F-046]:

```text
                  / \
                 /   \       Load Tests (3 scenarios) [F-044]
                / Chaos \     Chaos Tests (6 scenarios) [F-043]
               /---------\    E2E Tests (7 scenarios) [F-042]
              / Contract  \   Contract Tests (31 tests) [F-041]
             /-------------\  Integration Tests (135 tests) [F-036]-[F-040]
            /  Unit & UI    \ Unit Tests (27 Python + 99 Vitest) [F-035],[F-045]
           -------------------
```

| Level | Tool & Version | Primary Verification Target | Execution Environment | Test Count |
| :--- | :--- | :--- | :--- | :--- |
| **Unit (Backend)** | pytest 8.3.3 [F-026] | Pure domain functions, date math, money rounding, state machines | Local Workstation & CI runner | 27 tests (`libs/common`) [F-035] |
| **Unit & UI (Frontend)** | Vitest 2.1.9 [F-025] | React component rendering, permission guards, rule validators | Local Workstation & CI runner | 99 tests (17 files) [F-045] |
| **Integration** | pytest 8.3.3 [F-026] + Testcontainers 4.8.1 | Database queries, service routes, HTTP client retries | Local Workstation & CI runner | 135 tests (across 5 services) [F-036]–[F-040] |
| **Contract** | pytest 8.3.3 [F-026] | API payload schemas, Gateway route isolation, AMQP envelopes | Local Workstation & CI runner | 31 tests [F-041] |
| **E2E** | pytest 8.3.3 [F-026] + Docker Compose | Full cross-service sagas, correlation-ID tracing, outbox processing | Local Live Compose Stack | 7 tests [F-042] |
| **Chaos** | pytest 8.3.3 [F-026] + Docker API | Infrastructure failures, RabbitMQ/Redis/service downtime recovery | Local Live Compose Stack | 6 scenarios [F-043] |
| **Load** | k6 2.3.0 [F-027] | Throughput, p(95) latencies, database eventual convergence | Local Workstation (`compose.load`) | 3 scenarios [F-044] |

---

## 4. Test environments

1. **Unit/Integration Test Environment**: Runs in isolated ephemeral containers created via Testcontainers Python [F-017]–[F-026]. Each test execution spins up lightweight PostgreSQL 16-alpine containers [F-020] on random high-range ports.
2. **Full-Stack E2E & Chaos Environment**: Deploys the complete 15-container Docker Compose topology (`docker-compose.yml`) [F-001]–[F-016]. Services communicate over internal Docker DNS.
3. **CI Pipeline Environment**: Executes on GitHub Actions Ubuntu runners running Docker engine [F-067]. Runs `lint`, `tests`, `coverage`, `build`, and `live-stack` jobs.

---

## 5. Test data strategy

- **Unique Entity Identifiers**: Tests generate unique UUIDv4 keys and timestamped email addresses (`test_user_<uuid>@example.com`) to prevent state pollution across parallel test runs.
- **Seeded System Users**: Environment setup scripts seed fixed administrative accounts for contract verification (e.g. `admin@ems.local` with role `ADMIN` [F-068]).
- **Database Isolation & Cleanup**: Integration test fixtures wrap database interactions in explicit SQL transactions or drop temporary schemas post-test execution.

---

## 6. Entry and exit criteria (Quality gates)

### 6.1 Entry Criteria
- All Python backend code must pass Ruff syntax checks (`E9`, `F63`, `F7`, `F82`) with zero errors.
- Docker containers build without layer caching errors.

### 6.2 Exit Criteria (Thresholds)
- **Domain Coverage**: Every business service (`auth`, `employee`, `leave`, `payroll`, `notification`, `gateway`) must achieve >= 85.0% domain statement coverage [F-048]–[F-053].
- **Shared Library Coverage**: `libs/common` must achieve >= 80.0% overall statement coverage [F-047].
- **Test Pass Rate**: 100% of collected unit, integration, contract, e2e, and chaos tests must pass (0 failures).
- **Load Test Latency**: Average onboarding saga latency < 300 ms, read latency p(95) < 30 ms, with 0.00% request failure rate [F-054]–[F-058].
- **Database Convergence**: Post-load database outbox and state deltas must converge within 5.0 seconds [F-059].

---

## 7. Risk-based testing strategy

System components are prioritized based on operational failure severity:
1. **Critical Risk (Distributed Sagas & Payroll)**: Tested across all 5 pyramid layers (Unit, Integration, Contract, E2E, Chaos). Requires reverse compensation validation and outbox durability checks [F-060].
2. **High Risk (Auth & JWT RBAC)**: Tested via contract tests, permission matrix unit tests, and Gateway path isolation checks [F-028], [F-068].
3. **Medium Risk (Leave Balance Calculations)**: Tested via unit date math edge cases (leap years, weekends) and concurrency overlap checks [F-015], [F-030].
4. **Low Risk (Notifications & Telemetry)**: Tested via async consumer handlers and metric scraping checks [F-032], [F-065].

---

## 8. Defect management

Defects identified during automated or manual testing are cataloged in `docs/BUG_REPORTS.md` using the standard defect taxonomy [F-066]:

| Severity | Definition | Example Bug Recorded |
| :--- | :--- | :--- |
| **High** | System crash, data corruption, broken saga compensation, or startup failure | BUG-001 (Outbox signature), BUG-002 (Race condition), BUG-003 (Consumer reconnect loop) [F-066] |
| **Medium** | Functional mismatch, invalid UI state rendering, or non-blocking API error | BUG-004 (Blank leave balance field mismatch) [F-066] |
| **Low** | Minor UI alignment inconsistency or non-critical log formatting error | None recorded |

---

## 9. Metrics & reporting

Test execution reports are generated automatically by test runners:
- Pytest generates JUnit XML reports (`test-results.xml`) and HTML coverage reports (`htmlcov/`).
- Vitest outputs terminal test execution summaries.
- k6 outputs summary JSON metrics (`load_summary.json`).
- `scripts/check_docs.py` verifies document correctness and fact citation compliance.

---

## 10. Limitations of testing

1. **Single Workstation Bottlenecks**: Load and chaos tests execute on a single physical host machine hosting all 15 containers simultaneously [F-001]. Network latency represents internal Docker bridge performance rather than wide-area network latency.
2. **Development Default Credentials**: Test suites utilize non-sensitive development credentials defined in `.env.example` [F-068].
3. **CI Runner Host Mapping**: k6 load tests are executed locally and excluded from GitHub Actions CI due to Linux Docker container `host.docker.internal` DNS limitations [F-027].
