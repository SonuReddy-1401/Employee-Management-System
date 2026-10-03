# Student Inputs & Review 1 Project Documentation

## Title Page

- **Project Title**: Microservices-Based Employee Management System (EMS): Architecting for Scalability, High Concurrency, Fault Tolerance & Cluster Security
- **Course Name & Code**: Distributed Systems (DS / Sem 6)
- **Department**: Department of Computer Science & Engineering
- **College**: [Insert College Name, e.g., Department of Computer Science & Engineering]
- **Academic Year**: 2025–2026
- **Guide Name**: [Insert Guide / Professor Name]
- **Student Name(s) & Register Number(s)**:
  - Sonu Reddy ([Insert Register Number])

---

## Review 1 Summary & Architecture Comparison

### Problem Identified
Traditional monolithic Employee Management Systems suffer from tightly coupled components. In a monolith:
1. **Deployment Coupling**: Scaling a single feature (such as month-end payroll generation) requires re-deploying the entire monolithic application stack.
2. **Cascading Failure Risk**: A failure or unhandled exception in one non-critical module (e.g. notifications or leave calculation) causes a total application outage.
3. **Resource Contention**: High-concurrency surges during shift clock-in times (9:00 AM) or batch operations exhaust database connections and web server thread pools for all other services.

### Why a Distributed System is Required
By decomposing core business capabilities into independently deployable microservices, the system achieves:
- **Linear Horizontal Scaling**: High-volume write services (Attendance) and CPU-intensive calculation services (Payroll) can be scaled independently without allocating unnecessary resources to idle services.
- **Isolated Fault Domains**: Service failures are isolated within their pod domain. If the Notification service or RabbitMQ queue experiences a temporary delay, core HTTP operations (login, employee CRUD, clock-in) remain fully available.
- **Database-per-Service Isolation**: Each service owns its dedicated PostgreSQL schema, eliminating direct database coupling and preventing cross-domain locks.
- **Asynchronous Event-Driven Decoupling**: Non-blocking workloads (email notifications, audit logs, payslip generation alerts) are published to RabbitMQ, maintaining low API response latencies (<50ms).

### Proposed Solution
A microservices architecture engineered for high concurrency, fault tolerance, and cluster security:
- **API Gateway**: Nginx-based API Gateway handling SSL termination, CORS, JWT signature validation, and path routing (`/api/v1/employees`, `/api/v1/attendance`, `/api/v1/leave`, `/api/v1/payroll`, `/api/v1/auth`).
- **Core Microservices**: 6 domain services built with FastAPI (Auth & RBAC, Employee Directory, Attendance, Leave Management, Payroll, Notification).
- **Caching & Message Broker**: Redis cache layer for high-frequency profile reads (>80% hit ratio offload) and RabbitMQ message broker for async event streaming and Saga pattern orchestration.
- **Orchestration & Resilience**: Containerized via Docker Compose and Kubernetes manifest definitions with healthchecks, automated pod restarts, and chaos-tested queue resilience.

### Architecture Proposed in Review 1 vs. As Built
| Architectural Layer | Proposed in Review 1 | Implemented As Built |
| :--- | :--- | :--- |
| **API Gateway** | Nginx / Cloud Load Balancer with rate limiting and JWT routing | Nginx API Gateway with CORS, route forwarding, and Bearer JWT token verification |
| **Services** | 6 Microservices (Auth, Employee, Attendance, Leave, Payroll, Notification) | 6 FastAPI Microservices with modular domain logic and health endpoints |
| **Database Pattern** | Database-per-Service pattern | 5 Isolated PostgreSQL databases (`auth-db`, `employee-db`, `leave-db`, `payroll-db`, `notification-db`) |
| **Caching & Messaging** | Redis Cache & RabbitMQ event queue | Redis cache layer & RabbitMQ message broker with event consumers |
| **Distributed Transactions** | Saga pattern for multi-service onboarding | Compensating Saga orchestration across Auth, Employee, and Payroll services on failure |
| **Testing & Quality** | Unit & Integration testing | Vitest frontend suite (99 unit tests across 17 test files), Contract verification tests, RabbitMQ chaos suite, and Playwright E2E tests |

---

## Objectives

1. **Architect a Decoupled Microservices Infrastructure**: Enforce the Single Responsibility Principle and Database-per-Service isolation model to eliminate single points of failure.
2. **Implement Stateless JWT Authentication & RBAC**: Issue secure JWT tokens and enforce granular role-based permissions across `ADMIN`, `HR`, `MANAGER`, and `EMPLOYEE` roles.
3. **Build Real-Time Attendance & Work Logging**: Provide a day-of-week aligned calendar grid, historical date selection, early logoff detection (9 AM–5 PM rules), and hierarchical visibility controls.
4. **Orchestrate Distributed Transactions with Saga Pattern**: Implement multi-service onboarding workflows with automatic saga rollbacks (502 `ONBOARDING_FAILED`) when downstream services fail.
5. **Ensure High Concurrency & Low Latency**: Leverage Redis caching and RabbitMQ async queues to sustain heavy workloads during peak shift clock-ins.
6. **Validate System Resilience & Contract Safety**: Perform automated chaos testing (RabbitMQ message broker disruptions), contract verification testing, and full CI/CD pipeline automation.

---

## Individual Contribution

### Person / Role: Sonu Reddy
- **System Architecture & Design**: Designed the microservices boundaries, database-per-service isolation model, saga compensation flow for employee onboarding, and role-based access control policies.
- **Frontend & UI Engineering**: Implemented the dark zinc glassmorphism UI design system in React/Vite, including the Attendance Module calendar grid alignment, Date Selector, hierarchy table filter bar, and status badge indicators.
- **Backend & Saga Integration**: Implemented and refined API Gateway routing, JWT verification rules, error handling, and attendance/leave calculation logic.
- **Testing & Debugging**: Authored Vitest unit and integration test suites, fixed test assertions for asynchronous state changes, and created RabbitMQ chaos testing scripts (`test_03_leave_rabbitmq_chaos.py`).
- **Documentation & Verification**: Maintained project documentation including `ARCHITECTURE.md`, `CONTRACTS.md`, `TEST_PLAN.md`, `CHAOS_RESULTS.md`, `BUG_REPORTS.md`, and `STUDENT_INPUTS.md`.
- **Tools & AI Assistance (Honest Declaration)**:
  - Used **Antigravity (AI Coding Agent by Google DeepMind team)** to assist in refactoring microservice endpoints, writing Vitest component tests, configuring Docker Compose environment files, and resolving edge-case async test race conditions.
  - All AI-generated code was thoroughly reviewed, tested against local Docker containers, validated via Vitest unit tests, and verified through GitHub Actions CI pipeline execution.

---

## Evidence & Verification Links

- **GitHub Repository**: [https://github.com/SonuReddy-1401/Employee-Management-System](https://github.com/SonuReddy-1401/Employee-Management-System)
- **GitHub Actions Workflows**: [https://github.com/SonuReddy-1401/Employee-Management-System/actions](https://github.com/SonuReddy-1401/Employee-Management-System/actions)
- **Successful Green CI Pipeline Run**: [https://github.com/SonuReddy-1401/Employee-Management-System/actions/runs/37105655550](https://github.com/SonuReddy-1401/Employee-Management-System/actions/runs/37105655550)

### Annexures & Relevant Course Units (Distributed Systems)
- **Unit 1: Introduction to Distributed Systems**: System Models, Architectural Styles, Monolith vs Microservices.
- **Unit 2: Inter-process Communication & RPC**: RESTful APIs, HTTP/TLS Gateway Routing, JSON Payload Serialization.
- **Unit 3: Distributed Transactions & Consensus**: Saga Pattern, Compensating Transactions, Eventual Consistency over RabbitMQ.
- **Unit 4: Fault Tolerance & Resilience**: Health Checks, Circuit Breaking, Event Queue Resilience, Chaos Testing.
- **Unit 5: Distributed Security & Observability**: Stateless JWT Authentication, Role-Based Access Control, Prometheus/Grafana Telemetry.
