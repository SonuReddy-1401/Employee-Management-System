# CI Workflow & Local Rehearsal Documentation

This document describes the GitHub Actions Continuous Integration pipeline configured in `.github/workflows/ci.yml`.

## CI Pipeline Overview

The CI pipeline runs automatically on `push` to the `main` branch, all `pull_request` events, and manual `workflow_dispatch` triggers. It includes concurrency controls (`cancel-in-progress: true`), per-job timeout safety limits, and uses default development settings derived from `.env.example`.

---

## Workflow Jobs & Capabilities

### 1. `lint` Job
- **Purpose**: Validates Python code syntax and structural formatting using Ruff.
- **Proves**: Ensures no syntax errors (`E9`), invalid print/format specifiers (`F63`), invalid star imports (`F7`), or undefined variable names (`F82`) exist in the repository.
- **Expected Duration**: Not measured yet (pending first GitHub Actions runner execution).
- **Local Command**:
  ```bash
  python -m ruff check .
  ```
  *(or `make lint`)*

### 2. `tests` Job (Matrix Strategy)
- **Purpose**: Runs unit test suites across all components independently (`libs/common`, `services/auth`, `services/employee`, `services/leave`, `services/payroll`, `services/notification`, `services/gateway`).
- **Proves**: Verifies domain logic, schema validation, and API handler correctness for each isolated module.
- **Expected Duration**: Not measured yet.
- **Local Command**:
  ```bash
  python -m pytest <target_directory> -v
  ```

### 3. `coverage` Job
- **Purpose**: Executes `scripts/coverage.py` across all services and library components, collecting coverage metrics from `coverage.json`.
- **Proves**: Validates statement coverage against target thresholds (80.0% overall statement coverage for `libs/common`, 85.0% domain statement coverage for `/app/domain/` modules across services).
- **Measurement Details**: `scripts/coverage.py` measures overall statement coverage (`covered_lines / num_statements * 100.0` across all target files) and domain statement coverage (`covered_lines / num_statements * 100.0` across files matching `/app/domain/`).
- **Expected Duration**: Not measured yet.
- **Artifacts**: Uploads `docs/COVERAGE.md` and `coverage_reports/` directory as workflow build artifacts.
- **Local Command**:
  ```bash
  python scripts/coverage.py
  ```
  *(or `make coverage`)*

### 4. `build` Job
- **Purpose**: Builds Docker images for all microservices in parallel via Docker Compose.
- **Proves**: Verifies that all service Dockerfiles build cleanly without broken package installations or missing files.
- **Expected Duration**: Not measured yet.
- **Local Command**:
  ```bash
  cp .env.example .env
  docker compose build
  ```

### 5. `live-stack` Job
- **Purpose**: Spins up the full Docker Compose microservice stack with live PostgreSQL, Redis, and RabbitMQ dependencies, then runs smoke, contract, E2E, and chaos tests sequentially.
- **Proves**: Validates end-to-end multi-service interaction, schema contracts, transactional outbox publishing, event consumption, and resiliency under fault injection.
- **Expected Duration**: Not measured yet.
- **Artifacts**: Uploads `docker-compose-logs.log` on completion or failure.
- **Local Command**:
  ```bash
  cp .env.example .env
  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build --wait
  python scripts/smoke.py
  python -m pytest tests/contract -v
  python -m pytest tests/e2e -v
  python -m pytest tests/chaos -v -m chaos -s
  docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v
  ```

---

## Load Testing CI Constraint

Load tests (`scripts/load.py` & `tests/load/ems.js`) are deliberately **excluded** from the CI pipeline and reserved for local execution.

- **Technical Reason**: `scripts/load.py` executes `grafana/k6` inside a Docker container configured with `BASE_URL=http://host.docker.internal:8000`. `scripts/load.py` does not pass `--add-host=host.docker.internal:host-gateway` or `--network host` to `docker run`. On Linux CI runners (such as `ubuntu-latest`), Docker containers cannot resolve `host.docker.internal` without explicit host mapping flags, causing network connectivity failures.

---

## Configuration & Environment Security

- The CI workflow uses `.env.example` copied to `.env` for local and container configuration. `.env.example` contains non-sensitive development defaults only (`ADMIN_EMAIL`, default database user passwords, etc.). No real secrets or production credentials are embedded in repository workflow files.
