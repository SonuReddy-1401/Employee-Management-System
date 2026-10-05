# Employee Management System (EMS)

## Project Overview

The Employee Management System (EMS) is a microservices-based application composed of 15 containers `[F-001]` implementing employee directory management, leave approval processing, payroll calculations, and asynchronous event notifications. The backend microservices are built with Python 3.12-slim `[F-017]`, FastAPI 0.115.0 `[F-018]`, and SQLAlchemy 2.0.35 `[F-019]`, utilizing 5 dedicated PostgreSQL 16-alpine databases `[F-005]`, `[F-007]`, `[F-009]`, `[F-011]`, `[F-013]`, a RabbitMQ 3.13-management-alpine message broker `[F-021]`, and a Redis 7-alpine cache `[F-022]`. The user interface is a single-page application engineered with React 18.3.1 `[F-023]` and Vite 6.4.3 `[F-024]`, served by Nginx on port 8080 `[F-002]`.

## Key Features

- **Stateless Authentication & Role-Based Access Control**: JWT authentication supporting 4 distinct user roles (`ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`) `[F-068]`.
- **Employee Directory Management**: Onboarding saga orchestration across services, employee updates, soft-deletions, and filter capabilities `[F-029]`.
- **Leave Request & State Machine Engine**: Date range calculations excluding weekends, concurrency locking via `SELECT ... FOR UPDATE`, and remaining paid leave balance calculations `[F-030]`.
- **Payroll & Salary Deduction Processing**: Working days calculation, unpaid leave deduction formulas, and monthly payslip batch generation `[F-031]`.
- **Asynchronous Event Notifications**: Domain event streaming across RabbitMQ topic exchange `ems.events` `[F-033]` for 5 event types `[F-034]`, with idempotent consumer deduplication and email logging `[F-032]`.

## Architecture Overview

The system architecture enforces a Database-per-Service isolation pattern and event-driven decoupling. The Mermaid context diagram below shows all containerized components configured in `docker-compose.yml` `[F-001]`:

```mermaid
graph TB
    subgraph Client Layer
        Browser["User Web Browser"]
    end

    subgraph Edge & Web Layer
        Frontend["Frontend SPA (Nginx :8080 / :80)"]
        Gateway["API Gateway (:8000)<br/>- JWT Proxy Verification<br/>- Rate Limiter<br/>- Internal Route Shielding"]
    end

    subgraph Microservices Layer
        AuthSvc["Auth Service (:8001)<br/>- User Credentials<br/>- JWT Generation"]
        EmpSvc["Employee Service (:8002)<br/>- Employee Records<br/>- Onboarding Saga Orchestrator<br/>- Outbox Publisher"]
        LeaveSvc["Leave Service (:8003)<br/>- Leave Lifecycle Engine<br/>- Outbox Publisher"]
        PaySvc["Payroll Service (:8004)<br/>- Salary Engine<br/>- Payslip Generation<br/>- Event Consumer"]
        NotifSvc["Notification Service (:8005)<br/>- Simulated Emailer<br/>- Notification Feed<br/>- Event Consumer"]
    end

    subgraph Persistence & Caching Layer
        AuthDB[(Auth DB<br/>PostgreSQL)]
        EmpDB[(Employee DB<br/>PostgreSQL)]
        LeaveDB[(Leave DB<br/>PostgreSQL)]
        LeaveRedis[(Redis Cache<br/>Employee Snapshot)]
        PayDB[(Payroll DB<br/>PostgreSQL)]
        NotifDB[(Notification DB<br/>PostgreSQL)]
    end

    subgraph Message Broker Layer
        RMQ["RabbitMQ Broker (:5672 / :15672)<br/>Topic Exchange: ems.events"]
    end

    subgraph Observability Layer
        Prometheus["Prometheus (:9090)"]
        Grafana["Grafana (:3000)"]
    end

    %% Client Flow
    Browser -->|HTTP GET / Static Assets| Frontend
    Browser -->|HTTP REST APIs| Gateway

    %% Gateway Routing
    Gateway -->|/auth/*| AuthSvc
    Gateway -->|/employees/*| EmpSvc
    Gateway -->|/leaves/*| LeaveSvc
    Gateway -->|/payroll/* & /payslips/*| PaySvc
    Gateway -->|/notifications/*| NotifSvc

    %% Service Database Connections
    AuthSvc --- AuthDB
    EmpSvc --- EmpDB
    LeaveSvc --- LeaveDB
    LeaveSvc -.->|Cache Lookups / TTL 60s| LeaveRedis
    PaySvc --- PayDB
    NotifSvc --- NotifDB

    %% Inter-Service Synchronous Calls (Saga & Validation)
    EmpSvc -->|POST /internal/users| AuthSvc
    EmpSvc -->|POST /internal/profiles| PaySvc
    LeaveSvc -->|GET /employees/{id}| EmpSvc

    %% Event Outbox & Messaging Flow
    EmpDB -.->|Outbox Poller| RMQ
    LeaveDB -.->|Outbox Poller| RMQ
    RMQ -->|LeaveApproved / LeaveCancelled| PaySvc
    RMQ -->|All Domain Events| NotifSvc

    %% Observability Connections
    Prometheus -->|Scrape /metrics| Gateway
    Prometheus -->|Scrape /metrics| AuthSvc
    Prometheus -->|Scrape /metrics| EmpSvc
    Prometheus -->|Scrape /metrics| LeaveSvc
    Prometheus -->|Scrape /metrics| PaySvc
    Prometheus -->|Scrape /metrics| NotifSvc
    Grafana -->|Query Metrics| Prometheus
```

## Quick Start Guide

### Prerequisites
- Docker Engine & Docker Compose (15 containers `[F-001]`)
- Python 3.12-slim `[F-017]` (for running local test scripts)
- Node.js 22 LTS (for frontend local testing)

### Step 1: Environment Setup
Copy the example environment configuration file:
```bash
cp .env.example .env
```

### Step 2: Launch Application Stack
Start all container services in detached mode and wait for healthchecks:
```bash
docker compose up -d --wait
```

*Note*: Initial database table creation and default admin account seeding occur automatically during service startup lifecycle.

### Step 3: Access Ports & Application URLs

| Service / Interface | Published Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend SPA** | `8080` `[F-002]` | `80` `[F-002]` | Main Web Interface |
| **API Gateway** | `8000` `[F-003]` | `8000` `[F-003]` | Primary API Ingress Point |
| **Auth Service** | `8001` `[F-004]` | `8001` `[F-004]` | Identity & Auth Service |
| **Employee Service** | `8002` `[F-006]` | `8002` `[F-006]` | Employee Directory Service |
| **Leave Service** | `8003` `[F-008]` | `8003` `[F-008]` | Leave Management Service |
| **Payroll Service** | `8004` `[F-010]` | `8004` `[F-010]` | Payroll Processing Service |
| **Notification Service** | `8005` `[F-012]` | `8005` `[F-012]` | Event Notification Service |
| **RabbitMQ Management UI** | `15672` `[F-014]` | `15672` `[F-014]` | Message Broker Console |
| **Prometheus Telemetry** | `9090` `[F-016]` | `9090` `[F-016]` | Metrics Telemetry Server |
| **Grafana Dashboards** | `3000` | `3000` | Telemetry Dashboard Console |

*Note*: The development override file `docker-compose.dev.yml` publishes individual microservice ports directly to the host interface for local debugging.

## Demo Credentials

Refer to [`docs/DEMO.md`](file:///s:/CLG/DS/ems/docs/DEMO.md) for step-by-step instructions on accessing demo accounts. Initial credentials are configured via `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables in `.env`.

## Repository Layout

Verified repository structure matching `git ls-files` `[F-070]`:

```text
ems/
├── docker-compose.yml          # Production container composition
├── docker-compose.dev.yml      # Development port publishing override
├── docker-compose.load.yml     # Load testing configuration
├── Makefile                    # Task automation interface
├── README.md                   # Repository README
├── requirements-dev.txt        # Development dependencies
├── ruff.toml                   # Python linter configuration
├── docs/                       # Project documentation suite
├── frontend/                   # React 18 + Vite SPA single-page frontend
├── libs/                       # Shared Python libraries (ems_common)
├── observability/              # Prometheus and Grafana provisioning
├── scripts/                    # Utility, coverage, and load scripts
├── services/                   # Microservice applications
│   ├── auth/                   # Authentication service
│   ├── employee/               # Employee management service
│   ├── gateway/                # API Gateway proxy service
│   ├── leave/                  # Leave management service
│   ├── notification/           # Notification feed service
│   └── payroll/                # Payroll calculation service
└── tests/                      # Suite-level test specifications
    ├── chaos/                  # Failure injection chaos tests
    ├── contract/               # API & event contract verification tests
    ├── e2e/                    # End-to-end integration scenario tests
    └── load/                   # k6 load testing scenarios
```

## Test Execution Guide

Commands defined in [`Makefile`](file:///s:/CLG/DS/ems/Makefile) and project documentation:

### Unit & Integration Test Suite
Run unit and integration tests across all microservices and shared libraries using pytest 8.3.3 `[F-026]`:
```bash
pytest services/gateway services/auth services/employee services/leave services/payroll services/notification libs/common -v
```
*(Equivalent Makefile command: `make test`)*

### Contract Verification Test Suite
Run API contract and event envelope validation tests:
```bash
pytest tests/contract -v
```
*(Equivalent Makefile command: `make contract-test`)*

### End-to-End Test Suite
Run multi-service integration scenarios:
```bash
pytest tests/e2e -v
```
*(Equivalent Makefile command: `make e2e`)*

### Chaos Resilience Test Suite
Execute automated container failure injection and recovery scenarios:
```bash
python -m pytest tests/chaos -v -m chaos -s
```
*(Equivalent Makefile command: `make chaos`)*

### Load & Performance Test Suite
Execute k6 performance scenarios `[F-027]`:
```bash
python scripts/load.py
```
*(Equivalent Makefile command: `make load`)*

### Frontend Unit Test Suite
Execute frontend component unit tests using Vitest 2.1.9 `[F-025]`, `[F-045]`:
```bash
cd frontend && npm test -- --run
```

### Coverage Report Generation
Generate combined code coverage reports `[F-047]`:
```bash
python scripts/coverage.py
```
*(Equivalent Makefile command: `make coverage`)*

### Code Quality Linting
Run static linting with Ruff:
```bash
python -m ruff check .
```
*(Equivalent Makefile command: `make lint`)*

## CI/CD Pipeline Summary

The continuous integration pipeline executes automatically on GitHub Actions:
- **Pipeline URL**: [`https://github.com/SonuReddy-1401/Employee-Management-System/actions/runs/37105655550`](https://github.com/SonuReddy-1401/Employee-Management-System/actions/runs/37105655550) `[F-067]`
- The workflow provisions live PostgreSQL, Redis, and RabbitMQ services, runs frontend unit tests `[F-045]`, backend unit tests `[F-035]`–`[F-040]`, contract verification `[F-041]`, and end-to-end integration tests `[F-042]`.

## Documentation Index

| File Path | Description Summary |
| :--- | :--- |
| [`docs/ARCHITECTURE.md`](file:///s:/CLG/DS/ems/docs/ARCHITECTURE.md) | Full system architecture, Mermaid topology, microservice deep-dives, database ERDs, sagas, state machines, and outbox patterns. |
| [`docs/BUG_REPORTS.md`](file:///s:/CLG/DS/ems/docs/BUG_REPORTS.md) | Summary table, detection level analysis, root cause reports, fixes, and regression suites `[F-066]`. |
| [`docs/CHAOS_RESULTS.md`](file:///s:/CLG/DS/ems/docs/CHAOS_RESULTS.md) | Metrics and recovery times from fault-injection scenarios `[F-060]`–`[F-065]`. |
| [`docs/CI.md`](file:///s:/CLG/DS/ems/docs/CI.md) | Continuous Integration pipeline architecture, GitHub Actions config, and execution summary `[F-067]`. |
| [`docs/CONTRACTS.md`](file:///s:/CLG/DS/ems/docs/CONTRACTS.md) | REST endpoint specifications, JWT claims, event envelopes `[F-034]`, and message payloads. |
| [`docs/COVERAGE.md`](file:///s:/CLG/DS/ems/docs/COVERAGE.md) | Test coverage metrics for all services and common libraries `[F-047]`–`[F-053]`. |
| [`docs/DEMO.md`](file:///s:/CLG/DS/ems/docs/DEMO.md) | Step-by-step UI demonstration guide for supported roles `[F-068]`. |
| [`docs/DOC_RULES.md`](file:///s:/CLG/DS/ems/docs/DOC_RULES.md) | Rules and verification guidelines for documentation consistency. |
| [`docs/FACTS.md`](file:///s:/CLG/DS/ems/docs/FACTS.md) | Single source of truth for facts, metrics, and citations `[F-001]`–`[F-070]`. |
| [`docs/INDEX.md`](file:///s:/CLG/DS/ems/docs/INDEX.md) | Ordered reading guide for project review and examination. |
| [`docs/LOAD_RESULTS.md`](file:///s:/CLG/DS/ems/docs/LOAD_RESULTS.md) | k6 load test latency percentiles, throughput, and database convergence metrics `[F-054]`–`[F-059]`. |
| [`docs/REQUIREMENTS.md`](file:///s:/CLG/DS/ems/docs/REQUIREMENTS.md) | Functional and non-functional system requirements specification. |
| [`docs/TEST_PLAN.md`](file:///s:/CLG/DS/ems/docs/TEST_PLAN.md) | Strategy, environment setups, and test suite breakdowns across all levels. |
| [`docs/TRACEABILITY.md`](file:///s:/CLG/DS/ems/docs/TRACEABILITY.md) | Matrix linking system requirements to implementation code and test specifications. |
| [`docs/UI.md`](file:///s:/CLG/DS/ems/docs/UI.md) | Frontend component specs, page layouts, permission matrices, and constraints. |

## Known Limitations

- **Email Reservation on Onboarding Failure**: If an employee onboarding saga fails during downstream provision steps, the employee record remains with status `ONBOARDING_FAILED`. Reusing that email address returns HTTP 409 Conflict (documented in [`docs/ARCHITECTURE.md`](file:///s:/CLG/DS/ems/docs/ARCHITECTURE.md)).
- **Playwright Automated E2E Tests**: Playwright browser automated testing is not present in the current test suite (`frontend/e2e` directory does not exist `[F-046]`). Frontend testing is performed via Vitest unit tests `[F-045]` and backend contract/E2E suites.

## Security Notice

Credentials in `.env.example` are development defaults intended solely for local evaluation and testing. Production deployments must supply secure, randomly generated values for `JWT_SECRET`, `ADMIN_PASSWORD`, and database passwords.
