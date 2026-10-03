# Review 2 Presentation: Microservices-Based Employee Management System

## Slide 1: Title & Project Identification

### Slide Title
Microservices-Based Employee Management System (EMS): Architecting for Scalability, High Concurrency, Fault Tolerance & Cluster Security

### Bullet Points
- **Course & Code**: Distributed Systems (DS / Sem 6) [INPUT NEEDED: Course Code]
- **Department**: Department of Computer Science & Engineering
- **Institution**: [INPUT NEEDED: Insert College Name, e.g., Department of Computer Science & Engineering]
- **Academic Year**: 2025–2026
- **Project Guide**: [INPUT NEEDED: Insert Guide / Professor Name]
- **Presenter**: Sonu Reddy ([INPUT NEEDED: Insert Register Number])

### Visual Component
`docs/img/title_slide_banner.png`

### Speaker Notes
Good morning respected members of the evaluation panel and my project guide. I am Sonu Reddy, presenting our Review 2 evaluation for the Microservices-Based Employee Management System. This project addresses the core architectural challenges of legacy monolithic HR systems by decomposing core business capabilities into independently deployable microservices. Today, I will walk you through our final architecture, distributed systems patterns, automated chaos testing results, and live system demonstration.

### Facts Used
[INPUT NEEDED: Course Code], [INPUT NEEDED: Insert College Name], [INPUT NEEDED: Guide Name], [INPUT NEEDED: Register Number]

---

## Slide 2a: Problem Recap — Identified Monolithic Bottlenecks

### Slide Title
Problem Identified: Monolithic EMS Limitations

### Bullet Points
- **Deployment Coupling**: Scaling single high-volume features requires full monolith re-deployment.
- **Cascading Failure Risk**: Unhandled errors in non-critical modules cause complete system outages.
- **Resource Contention**: High-concurrency shift clock-in surges exhaust database connection pools.
- **Tightly Coupled Schema**: Shared database tables create cross-domain lock contention.
- **Monolithic Bottlenecks**: Inability to scale CPU-intensive payroll calculations independently.

### Visual Component
`docs/img/monolith_bottlenecks.png`

### Speaker Notes
Traditional monolithic Employee Management Systems suffer from tight coupling. A single failure in a background feature like leave calculations can crash the entire web process, preventing employees from logging in or marking attendance. Furthermore, during peak morning hours around 9:00 AM, shift clock-in concurrency exhausts database connections across all application modules simultaneously. Re-deploying a small bug fix requires building and deploying the entire monolithic codebase.

### Facts Used
None (Derived strictly from `docs/STUDENT_INPUTS.md:18-23`).

---

## Slide 2b: Problem Recap — Why a Distributed System is Required

### Slide Title
Why a Distributed System is Required

### Bullet Points
- **Student Justification**: Achieves linear horizontal scaling, isolated fault domains, and non-blocking async decoupling.
- **Independent Deployment**: Microservices update independently without re-deploying the full stack [F-001].
- **Fault Isolation**: RabbitMQ outage does not block HTTP leave creation; requests are buffered in outbox [F-062].
- **Independent Scaling**: Attendance and Payroll services scale CPU/RAM independently across containers [F-006], [F-010].
- **Empirical Evidence**: Chaos test S3 proved leave approval succeeds (200 OK) during RabbitMQ outages with 6.13s post-recovery delivery [F-062].

### Visual Component
`docs/img/why_distributed_system.png`

### Speaker Notes
A distributed architecture solves monolithic bottlenecks through four key capabilities. First, independent deployment allows individual microservices to be updated without taking down other modules. Second, fault isolation ensures system availability—for instance, in Chaos Scenario S3, when our RabbitMQ message broker went down, users could still approve leaves with 200 OK responses because events were buffered in outbox tables and delivered post-recovery within 6.13 seconds [F-062]. Third, CPU-heavy services like Payroll can scale independently from read-heavy services like Directory [F-006], [F-010].

### Facts Used
[F-001], [F-006], [F-010], [F-062]

---

## Slide 2c: Problem Recap — Proposed Solution from Review 1

### Slide Title
Proposed Solution from Review 1

### Bullet Points
- **API Gateway Layer**: Nginx Gateway providing SSL, CORS, JWT signature validation, and path routing (`/api/v1/*`).
- **Core Business Microservices**: 6 domain microservices built with FastAPI (Auth, Employee, Attendance, Leave, Payroll, Notification).
- **Caching Layer**: Redis cache offloading high-frequency employee profile reads.
- **Async Messaging**: RabbitMQ broker enabling event streaming and compensating Saga orchestration.
- **Resilient Containerization**: Containerized via Docker Compose with health checks and automated restarts.

### Visual Component
`docs/img/proposed_solution_review1.png`

### Speaker Notes
Our Review 1 proposal outlined a modern microservices architecture built around 6 core domain microservices. An Nginx API Gateway serves as the single entry point, handling JWT verification, CORS policy enforcement, and request routing. To handle high concurrency, Redis caches employee profile queries, while RabbitMQ manages non-blocking event publishing and distributed Saga transactions across service boundaries. This foundation established our decoupling strategy for scalability and fault tolerance.

### Facts Used
None (Derived strictly from `docs/STUDENT_INPUTS.md:31-36`).

---

## Slide 3: Final Proposed Architecture vs. As Built

### Slide Title
Final Proposed Architecture & Implementation Delta

### Bullet Points
- **Container Topology**: 15 Docker containers running gateway, 6 microservices, 5 PostgreSQL databases, Redis, RabbitMQ, Prometheus [F-001].
- **Service Catalogue**: Auth (:8001), Employee (:8002), Leave (:8003), Payroll (:8004), Notification (:8005) [F-004]–[F-013].
- **Gateway Implementation**: Nginx API Gateway (:8000) verifying Bearer JWT tokens statelessly [F-003], [F-068].
- **Database-per-Service**: 5 dedicated database containers (`auth-db`, `employee-db`, `leave-db`, `payroll-db`, `notification-db`) [F-005]–[F-013].
- **Architecture Delta**: Review 1 proposed K8s deployment; as built, Docker Compose orchestration was implemented with 99 Vitest UI tests [F-045] and 180 Pytest tests [F-035]–[F-044].

### Visual Component
`docs/img/architecture_container_diagram.png`

### Speaker Notes
This slide illustrates our final containerized architecture as built. All 15 containers run on an isolated Docker network [F-001]. The API Gateway forwards verified client requests to microservices while blocking unauthenticated access. Each microservice exclusively owns its database instance [F-005]–[F-013]. Compared to Review 1, our implementation refined the test infrastructure, delivering 99 Vitest component tests [F-045] and 180 backend test cases [F-035]–[F-044].

### Facts Used
[F-001], [F-003], [F-004]–[F-013], [F-035]–[F-045], [F-068]

---

## Slide 4: Implementation / Prototype Overview

### Slide Title
System Implementation & Codebase Statistics

### Bullet Points
- **Codebase Metrics**: 295 total files, 24,139 lines of code across 32 git commits [F-069], [F-070].
- **Language Breakdown**: 11,997 lines Python (.py), 3,800 lines React JSX (.jsx), 1,088 lines JS (.js) [F-070].
- **UI Screens**: 8 interactive screens (/login, /dashboard, /employees, /leave, /attendance, /payroll, /notifications, /system) [F-068].
- **Role Visibility**: Enforces RBAC permissions across ADMIN, HR, MANAGER, and EMPLOYEE roles [F-068].
- **Frontend Architecture**: SPA built with React 18.3.1 [F-023], Vite 6.4.3 [F-024], served via Nginx Alpine [F-002].

### Visual Component
`docs/img/ui_dashboard_overview.png`

### Speaker Notes
Our prototype is fully implemented and operational in code. The repository contains 295 total files and 24,139 lines of production and test code [F-070]. The user interface provides 8 role-guarded screens, including Dashboard, Employee Directory, Attendance Calendar, Leave Management, Batch Payroll, Notifications, and System Telemetry [F-068]. All UI views adapt dynamically to enforce role-based access control policies across user sessions.

### Facts Used
[F-002], [F-023], [F-024], [F-068], [F-069], [F-070]

---

## Slide 5: Technologies Used

### Slide Title
Technology Stack & Component Roles

### Bullet Points
- **Python 3.12-slim**: Core microservices runtime environment [F-017].
- **FastAPI 0.115.0 & SQLAlchemy 2.0.35**: High-performance HTTP routing and ORM data mapping [F-018], [F-019].
- **PostgreSQL 16-alpine**: Isolated relational data stores for each microservice [F-020].
- **RabbitMQ 3.13-management-alpine**: AMQP 5672 message broker for event distribution [F-021].
- **Redis 7-alpine & Nginx Alpine**: In-memory caching [F-022] and SPA static serving / Gateway reverse proxy [F-002].
- **React 18.3.1, Vite 6.4.3, Vitest 2.1.9, pytest 8.3.3**: Frontend SPA, build tooling, and test runners [F-023]–[F-026].

### Visual Component
`docs/img/tech_stack_table.png`

### Speaker Notes
Our technology choices prioritize high performance, type safety, and developer efficiency. The backend uses Python 3.12 with FastAPI 0.115 and SQLAlchemy 2.0 ORM mapping [F-017]–[F-019]. PostgreSQL 16 powers our 5 microservice databases [F-020], while RabbitMQ 3.13 manages asynchronous messaging [F-021]. The frontend uses React 18 and Vite 6 [F-023], [F-024], verified by Vitest 2.1 [F-025] and pytest 8.3 [F-026] to ensure full stack reliability.

### Facts Used
[F-002], [F-017]–[F-026]

---

## Slide 6: Distributed Systems Patterns Implementation

### Slide Title
Verified Distributed Systems Patterns

### Bullet Points
- **Service Decomposition**: 6 domain microservices (`services/employee/app/main.py:1`).
- **Database per Service**: 5 isolated PostgreSQL containers (`docker-compose.yml:25`) [F-005]–[F-013].
- **API Gateway**: Nginx routing & JWT auth (`services/gateway/app/main.py:1`) [F-003].
- **Transactional Outbox**: Atomic event staging (`libs/common/ems_common/outbox.py:10`).
- **Idempotent Consumer**: Duplicate detection via `processed_events` (`libs/common/ems_common/consumer.py:25`).
- **Saga with Compensation**: Multi-service onboarding rollback (`services/employee/app/domain/saga.py:15`).

### Visual Component
`docs/img/distributed_patterns_map.png`

### Speaker Notes
This slide summarizes 6 key distributed systems patterns implemented in EMS. We enforce Database-per-Service across 5 PostgreSQL instances to ensure strict data isolation [F-005]–[F-013]. To guarantee reliability across service boundaries, we implement Transactional Outbox for atomic event publishing, Idempotent Consumers with duplicate detection tables, and Saga Orchestration with automatic compensation whenever downstream microservices experience unexpected failure during multi-step workflows. This design guarantees resilience across all distributed components.

### Facts Used
[F-003], [F-005]–[F-013]

---

## Slide 7: System Workflow — Onboarding Saga & Leave-to-Payroll

### Slide Title
End-to-End System Workflows

### Bullet Points
- **Onboarding Saga Step 1**: Client posts employee data; Employee service creates `PENDING_ONBOARDING` record (`POST /employees`) [F-029].
- **Onboarding Saga Step 2 & 3**: Employee service synchronously calls Auth (`POST /internal/users`) [F-028] and Payroll (`POST /internal/profiles`) [F-031].
- **Saga Compensation**: On Payroll HTTP 500 failure, Employee service issues `DELETE /internal/users/{id}`, marks status `ONBOARDING_FAILED`, returns HTTP 502 [F-060].
- **Leave-to-Payroll Flow Step 1**: Manager approves leave (`POST /leaves/{id}/approve`); Leave service writes `LeaveApproved` outbox row [F-030].
- **Leave-to-Payroll Flow Step 2**: Outbox publisher streams event over RabbitMQ exchange `ems.events` [F-033]; Payroll & Notification consume event asynchronously [F-034].

### Visual Component
`docs/img/sequence_onboarding_saga.png`

### Speaker Notes
Here we highlight two core system workflows. The Onboarding Saga creates user credentials across Employee, Auth, and Payroll services synchronously. If Payroll fails, the saga triggers reverse compensation by deleting created Auth credentials and setting status to `ONBOARDING_FAILED` [F-060]. The Leave-to-Payroll workflow uses asynchronous event streaming—leave approvals stage an outbox row, which is published to RabbitMQ and consumed by Payroll for deduction calculations and Notification for email logging [F-033], [F-034].

### Facts Used
[F-028]–[F-031], [F-033], [F-034], [F-060]

---

## Slide 8: Fault Tolerance & Chaos Injection Results

### Slide Title
Chaos Injections & Measured Recovery Times

### Bullet Points
- **Chaos S1 (Payroll Down)**: Payroll down during onboarding -> Saga returns 502 `ONBOARDING_FAILED`, Auth compensated, recovery **0.43s** [F-060].
- **Chaos S2 (Auth Down)**: Auth down during onboarding -> Saga returns 502 `ONBOARDING_FAILED`, zero orphaned records, recovery **0.43s** [F-061].
- **Chaos S3 (RabbitMQ Outage)**: Broker down -> Leave approved (200 OK), outbox buffered, published post-recovery, recovery **6.13s** [F-062].
- **Chaos S4 (Notification Outage)**: Notification service down -> Events buffered in RabbitMQ, zero duplicate notifications, recovery **0.18s** [F-063].
- **Chaos S5 (Redis Outage)**: Cache down -> Direct HTTP fallback to Employee service succeeds synchronously, recovery **N/A (Fallback)** [F-064].

### Visual Component
`docs/img/chaos_results_summary.png`

### Speaker Notes
To prove system resilience, we conducted 5 automated chaos testing scenarios. In Chaos S1 and S2, microservice outages during employee onboarding triggered instant saga compensation in 0.43 seconds with zero orphaned database rows [F-060], [F-061]. In Chaos S3, stopping the RabbitMQ broker did not interrupt HTTP leave approvals—events were safely staged in outbox tables and delivered within 6.13 seconds post-recovery [F-062]. In Chaos S5, Redis outages were transparently handled via direct HTTP fallback [F-064].

### Facts Used
[F-060], [F-061], [F-062], [F-063], [F-064]

---

## Slide 9: Performance & Load Testing Results

### Slide Title
Load Scenario Performance & Database Convergence

### Bullet Points
- **Read Workload (`reads`)**: `GET /employees` averaged 13.83 ms, p(95) **25.92 ms** across 1,729 iterations with 0.00% failure [F-054].
- **Leave Creation (`create_leave`)**: `POST /leaves` averaged 75.64 ms, p(95) **204.55 ms** across 4,940 iterations with 0.00% failure [F-055].
- **Leave Approval (`approve_leave`)**: `POST /leaves/{id}/approve` averaged 52.12 ms, p(95) **153.79 ms** across 4,940 iterations with 0.00% failure [F-056].
- **Onboarding Saga (`onboarding`)**: `POST /employees` averaged 269.40 ms, p(95) **296.90 ms** across 120 iterations with 0.00% failure [F-057].
- **Total Checks & Convergence**: 28,398 total k6 checks passed (100.00% pass rate) [F-058]; outbox database deltas converged in **3.37 seconds** [F-059].
- **Measurement Limits**: Executed on a single development workstation hosting all 15 containers simultaneously [F-054]–[F-059].

### Visual Component
`docs/img/load_testing_k6_charts.png`

### Speaker Notes
Our load testing suite executed 4 concurrent scenarios using k6 [F-054]–[F-057]. Directory reads achieved a p(95) latency of 25.92 ms [F-054], leave approvals achieved a p(95) of 153.79 ms [F-056], and cross-service onboarding sagas completed in a p(95) of 296.90 ms [F-057]. Across 28,398 assertions, we achieved a 100% pass rate with zero HTTP errors [F-058]. Database event counts converged completely within 3.37 seconds post-load [F-059].

### Facts Used
[F-054], [F-055], [F-056], [F-057], [F-058], [F-059]

---

## Slide 10: Test Pyramid & Quality Analysis

### Slide Title
Test Coverage & Defect Audit Summary

### Bullet Points
- **Test Pyramid**: 180 Pytest backend tests [F-035]–[F-044] + 99 Vitest frontend tests [F-045] = 279 total automated tests.
- **Service Coverage**: Domain coverage achieved 100% in Auth, Employee, Notification, Gateway, 98.1% in Leave, 98.5% in Payroll [F-048]–[F-053].
- **Shared Library Coverage**: `libs/common` achieved 89.9% overall statement coverage [F-047].
- **Defects Found & Resolved**: 4 system bugs identified and resolved during audit (BUG-001 through BUG-004) [F-066].
- **Quality Insights**: High unit/contract coverage proved API safety; load tests confirmed zero thread deadlock under concurrency [F-058].

### Visual Component
`docs/img/test_pyramid_coverage.png`

### Speaker Notes
Our comprehensive quality assurance strategy combines unit, contract, e2e, chaos, and UI testing across 279 automated test cases [F-035]–[F-045]. Domain code coverage reached 100% across Auth, Employee, Notification, and Gateway services [F-048], [F-049], [F-052], [F-053]. During test auditing, we identified and resolved 4 critical system defects—including outbox signature mismatches and consumer reconnection deadlocks [F-066]—ensuring exceptionally high architectural integrity across all microservices.

### Facts Used
[F-035]–[F-046], [F-047]–[F-053], [F-066]

---

## Slide 11: Live Demonstration & Screen Walkthrough

### Slide Title
Live System Demonstration Script (8 Steps)

### Bullet Points
- **Step 1: Admin Login**: Log in as `admin@ems.local`; verify JWT token storage and role-based redirect (`/dashboard`) [F-068].
- **Step 2: Employee Onboarding**: Onboard new employee via `/employees` modal; verify 201 Created response [F-029].
- **Step 3: Saga Failure Test**: Attempt onboard with duplicate email; verify 502 `ONBOARDING_FAILED` toast and auth rollback [F-060].
- **Step 4: Clock-In & Early Logoff**: Switch to Employee login; mark attendance and trigger early logoff alert (`/attendance`).
- **Step 5: Leave Application**: Submit 3-day leave request (`/leave`); verify weekday validation and balance deduction [F-030].
- **Step 6: Manager Approval**: Log in as Manager; approve pending team leave request (`/leave`); verify `LeaveApproved` outbox event [F-030].
- **Step 7: Payroll Run & Payslip**: Log in as HR; execute monthly payroll run (`/payroll`); open payslip breakdown modal [F-031].
- **Step 8: System Telemetry**: Open `/system`; view real-time health checks (UP/DOWN) and Grafana/RabbitMQ links [F-016].

### Visual Component
`docs/img/demo_script_screen.png`

### Speaker Notes
Our live demonstration follows an 8-step operational script. We begin by logging in as Admin to onboard employees [F-068], demonstrate saga compensation when creating duplicate users [F-060], show employee clock-in and early logoff detection on the Attendance calendar grid, submit and approve leave requests across Manager hierarchies [F-030], run batch payroll with payslip breakdown modals [F-031], and inspect real-time system health checks on the Telemetry page [F-016].

### Facts Used
[F-016], [F-029], [F-030], [F-031], [F-060], [F-068]

---

## Slide 12: Challenges Faced & Technical Solutions

### Slide Title
Engineering Challenges & Resolution Matrix

### Bullet Points
- **Challenge 1 (Outbox Publisher)**: Invalid function signature in Leave outbox publisher -> Fixed in `libs/common` (BUG-001) [F-066].
- **Challenge 2 (FastAPI Yield Race)**: Database session closed before response sent -> Moved commit before yield in dependency (BUG-002) [F-066].
- **Challenge 3 (Startup Reconnect)**: Consumers failed permanently when broker unreachable at startup -> Implemented exponential backoff loop (BUG-003) [F-066].
- **Challenge 4 (UI Mismatch)**: Blank leave balance displayed due to field name mismatch -> Aligned API schema transformer (BUG-004) [F-066].
- **Challenge 5 (RabbitMQ Outage)**: Broker down during leave approval -> Implemented Transactional Outbox pattern, recovery in 6.13s (Chaos S3) [F-062].
- **[INPUT NEEDED: other challenges]**: Optional student-specific challenges encountered during local setup.

### Visual Component
`docs/img/challenges_matrix.png`

### Speaker Notes
During development and chaos auditing, we resolved 5 major technical challenges [F-066]. For instance, BUG-003 caused event consumers to terminate permanently if RabbitMQ was slow to start; we resolved this by engineering an exponential backoff reconnect loop. In BUG-002, FastAPI yield dependencies closed database sessions prematurely, which we fixed by enforcing explicit commit ordering. Chaos scenario S3 validated that our Transactional Outbox safely buffers events during broker downtime [F-062].

### Facts Used
[F-062], [F-066], [INPUT NEEDED: other challenges]

---

## Slide 13: Conclusion, System Limitations & Future Work

### Slide Title
Conclusion & Project Summary

### Bullet Points
- **Key Achievements**: 15 containerized services [F-001], 6 microservices, 279 automated tests [F-035]–[F-045], 100% check pass rate [F-058], green CI pipeline [F-067].
- **System Limitations**: Reusing failed onboarding emails returns 409 conflict; gateway rate limits shared behind Nginx proxy [F-068].
- **Future Work (Not Implemented)**: Apache Kafka migration for long-term log retention.
- **Future Work (Not Implemented)**: Kubernetes HPA auto-scaling and Helm chart packaging.
- **Future Work (Not Implemented)**: Distributed tracing backend integration using OpenTelemetry and Jaeger.

### Visual Component
`docs/img/conclusion_summary.png`

### Speaker Notes
In conclusion, the Microservices-Based Employee Management System successfully satisfies all distributed systems objectives. We delivered 15 containerized services [F-001], 6 microservices, 279 automated tests [F-035]–[F-045], and 100% load test pass rates [F-058], verified by a green GitHub Actions CI pipeline [F-067]. Future enhancements will focus on Kubernetes HPA auto-scaling, Apache Kafka event streaming, and OpenTelemetry distributed tracing. Thank you, and I welcome your questions.

### Facts Used
[F-001], [F-035]–[F-045], [F-058], [F-067], [F-068]
