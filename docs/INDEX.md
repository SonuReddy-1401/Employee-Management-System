# Documentation Reading Guide & Index

This document serves as an ordered reading guide for evaluators, examiners, and developers reviewing the Employee Management System (EMS).

---

## 1. Where to Start First (2-Minute Overview)

Start with the primary repository files to understand the high-level architecture and quick setup:

1. **[`README.md`](file:///s:/CLG/DS/ems/README.md)**: High-level system overview, technology stack versions `[F-017]`–`[F-024]`, container topology `[F-001]`, port mappings `[F-002]`–`[F-016]`, quick start guide, test execution commands, and document index.
2. **[`docs/INDEX.md`](file:///s:/CLG/DS/ems/docs/INDEX.md)**: This reading guide.

---

## 2. 10-Minute Reading Track (Core Architecture & Single Source of Truth)

For a fast evaluation of project facts, architecture design, and features:

1. **[`docs/FACTS.md`](file:///s:/CLG/DS/ems/docs/FACTS.md)**: Single source of truth for all system quantitative metrics, container counts `[F-001]`, endpoint counts `[F-028]`–`[F-032]`, test suite counts `[F-035]`–`[F-046]`, coverage metrics `[F-047]`–`[F-053]`, performance metrics `[F-054]`–`[F-059]`, and chaos metrics `[F-060]`–`[F-065]`.
2. **[`docs/ARCHITECTURE.md`](file:///s:/CLG/DS/ems/docs/ARCHITECTURE.md)**: System topology, microservice deep-dives, Database-per-Service isolation, Mermaid Entity-Relationship Diagrams, Employee Onboarding Saga sequence diagram, Leave state machine, and Transactional Outbox pattern.
3. **[`docs/DEMO.md`](file:///s:/CLG/DS/ems/docs/DEMO.md)**: Step-by-step user interface demonstration guide covering login, onboarding, leave management, payroll execution, notifications, and telemetry across supported roles (`ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`) `[F-068]`.

---

## 3. 1-Hour Comprehensive Review (Deep Dive into Verification & Quality)

For a complete academic and technical audit of the codebase, contracts, testing, and operational results:

### A. System Specifications & Contracts
1. **[`docs/CONTRACTS.md`](file:///s:/CLG/DS/ems/docs/CONTRACTS.md)**: Endpoint payload details, HTTP status codes, JWT claims, role permissions, and RabbitMQ topic exchange `ems.events` event contracts `[F-033]`, `[F-034]`.
2. **[`docs/REQUIREMENTS.md`](file:///s:/CLG/DS/ems/docs/REQUIREMENTS.md)**: Detailed functional and non-functional system requirements.
3. **[`docs/UI.md`](file:///s:/CLG/DS/ems/docs/UI.md)**: Frontend Single Page Application architecture, page specs, permission matrix, and technical constraints.

### B. Quality Assurance, Testing & Coverage
4. **[`docs/TEST_PLAN.md`](file:///s:/CLG/DS/ems/docs/TEST_PLAN.md)**: Multi-level test strategy covering unit, integration, contract, E2E, chaos, and load testing.
5. **[`docs/COVERAGE.md`](file:///s:/CLG/DS/ems/docs/COVERAGE.md)**: Component-by-component statement and domain test coverage metrics `[F-047]`–`[F-053]`.
6. **[`docs/BUG_REPORTS.md`](file:///s:/CLG/DS/ems/docs/BUG_REPORTS.md)**: Summary table of recorded system bugs `[F-066]`, detection level analysis, detailed root cause reports, fixes, and regression test suites.
7. **[`docs/TRACEABILITY.md`](file:///s:/CLG/DS/ems/docs/TRACEABILITY.md)**: Matrix connecting functional requirements to source code implementations and test suites.

### C. Operational & Performance Verification
8. **[`docs/CHAOS_RESULTS.md`](file:///s:/CLG/DS/ems/docs/CHAOS_RESULTS.md)**: Fault-injection test outcomes (database outages, broker failures, Redis fallbacks) and recovery time measurements `[F-060]`–`[F-065]`.
9. **[`docs/LOAD_RESULTS.md`](file:///s:/CLG/DS/ems/docs/LOAD_RESULTS.md)**: Performance benchmarks measured with k6 load runner `[F-027]`, including request latencies, throughput, and database state convergence `[F-054]`–`[F-059]`.
10. **[`docs/CI.md`](file:///s:/CLG/DS/ems/docs/CI.md)**: GitHub Actions continuous integration pipeline architecture and automated execution summary `[F-067]`.
11. **[`docs/STUDENT_INPUTS.md`](file:///s:/CLG/DS/ems/docs/STUDENT_INPUTS.md)**: Academic project overview, review summaries, individual contributions, and green CI pipeline run URL `[F-067]`.
12. **[`docs/DOC_RULES.md`](file:///s:/CLG/DS/ems/docs/DOC_RULES.md)**: Documentation standards, fact citation rules, and verification criteria.
