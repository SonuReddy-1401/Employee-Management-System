# Viva Voice Preparation: 25 Examiner Questions & Answers

## Question 1: Why did you choose a Microservices architecture instead of a Monolith?
**Answer**: Monolithic systems suffer from deployment coupling, cascading failures, and database connection exhaustion during peak clock-in times [F-001]. Microservices decompose core domain capabilities into independently deployable containers [F-001], enabling independent horizontal scaling of high-load services like Payroll [F-010] and fault domain isolation so that queue delays do not crash HTTP API endpoints [F-062].

## Question 2: Why do you enforce the Database-per-Service pattern?
**Answer**: Database-per-Service ensures strict domain isolation and data ownership [F-005]–[F-013]. Each service owns its dedicated PostgreSQL schema container (`auth-db`, `employee-db`, `leave-db`, `payroll-db`, `notification-db`) [F-005]–[F-013]. Direct cross-service database access or SQL joins are strictly forbidden, eliminating cross-domain table locks and enabling independent database schema migration.

## Question 3: Why use the Saga pattern instead of Two-Phase Commit (2PC) for distributed transactions?
**Answer**: 2PC relies on synchronous, blocking locks across distributed database nodes, creating high latency, tight coupling, and low availability if any database node fails. The Saga pattern executes a sequence of local transactions across services (`services/employee/app/domain/saga.py:15`). If a downstream step fails (e.g. Payroll HTTP 500), the Saga orchestrator triggers explicit reverse compensating calls (`DELETE /internal/users/{id}`) to restore system consistency asynchronously without holding database locks [F-060].

## Question 4: What specific problem does the Transactional Outbox pattern solve in your system?
**Answer**: Writing to a relational database and publishing an AMQP message to RabbitMQ in a single request cannot be performed in a single atomic transaction without 2PC (`libs/common/ems_common/outbox.py:10`). The Transactional Outbox pattern writes domain entities and pending event records into the same local PostgreSQL database in a single ACID transaction. A background publisher loop polls the outbox table and streams events to RabbitMQ [F-033], guaranteeing zero lost events even if the message broker is temporarily offline [F-062].

## Question 5: What happens to the system if the RabbitMQ message broker goes down completely?
**Answer**: Core HTTP synchronous operations (login, employee CRUD, leave creation, leave approval) continue operating normally and return 200 OK responses to clients [F-062]. Domain events generated during broker downtime are safely staged in PostgreSQL outbox tables. When RabbitMQ recovers, the outbox publisher automatically reconnects and flushes all pending events within 6.13 seconds without event loss [F-062].

## Question 6: How does the system handle duplicate event delivery from message queues?
**Answer**: All consumers implement Idempotent Consumer handlers using a `processed_events` table in PostgreSQL (`libs/common/ems_common/consumer.py:25`). When a consumer receives an event, it checks if the event's unique `event_id` exists in its local database before processing. Duplicate events are silently acknowledged (ACK) and skipped, preventing duplicate payroll deductions or duplicate notification logs [F-063].

## Question 7: Where does your system stand regarding the CAP Theorem?
**Answer**: EMS chooses **Availability (A)** and **Partition Tolerance (P)** over immediate Consistency (C), adopting an **Eventual Consistency** model [F-059]. During network partitions or broker outages, services process local reads/writes independently. Eventual consistency across Payroll and Notification domain states converges within 3.37 seconds post-recovery [F-059].

## Question 8: How does the Circuit Breaker work, and what are its exact settings?
**Answer**: The HTTP client implements a Circuit Breaker pattern to prevent cascading caller thread exhaustion during downstream service outages (`libs/common/ems_common/http_client.py:45`). When 5 consecutive HTTP request failures occur within a rolling 60-second window, the circuit trips to an `OPEN` state, immediately failing subsequent requests for 30 seconds before attempting a `HALF-OPEN` probe request.

## Question 9: How is cluster security and authorization implemented?
**Answer**: Security is enforced at the Nginx API Gateway using stateless Bearer JWT tokens [F-003], [F-068]. The Gateway decodes the JWT signature, extracts the user's `sub` (employee ID) and `role` (`ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`), forwards claims as HTTP headers (`X-User-Id`, `X-User-Role`), and blocks unauthenticated requests with HTTP 401 [F-028], [F-068].

## Question 10: What capabilities are currently NOT implemented in the prototype?
**Answer**: Not implemented features include: automated Kubernetes HPA pod scaling [F-001], Apache Kafka long-term audit logging, multi-region database replication, OpenTelemetry distributed tracing, and mobile native apps. Additionally, reusing a failed onboarding email address currently returns an HTTP 409 conflict [F-068].

## Question 11: How was automated testing organized across the codebase?
**Answer**: Testing follows a 5-layer pyramid: 27 Python unit tests [F-035], 99 Vitest UI component tests [F-045], 135 integration tests [F-036]–[F-040], 31 OpenAPI contract tests [F-041], 7 Playwright E2E tests [F-042], 6 RabbitMQ chaos tests [F-043], and 3 k6 load scenarios [F-044] = 279 total automated tests.

## Question 12: Which system bugs were discovered during testing, and how were they fixed?
**Answer**: 4 bugs were identified and fixed [F-066]: BUG-001 (invalid outbox function signature in Leave service), BUG-002 (FastAPI session closed prematurely due to yield ordering), BUG-003 (consumer reconnect loop terminating on slow broker startup), and BUG-004 (UI blank leave balance due to field name mismatch).

## Question 13: How was scalability measured, and what were the measurement boundaries?
**Answer**: Scalability was evaluated using 4 k6 load test scenarios (`reads`, `create_leave`, `approve_leave`, `onboarding`) totaling 28,398 checks [F-054]–[F-058]. Measurement limits: tests executed on a single development workstation hosting all 15 Docker containers simultaneously [F-001].

## Question 14: Why did you deploy using Docker Compose instead of Kubernetes?
**Answer**: Docker Compose provides lightweight container orchestration, deterministic networking, and low resource overhead suitable for workstation-based development and CI pipeline automation [F-001], [F-067]. Kubernetes manifests were specified in Review 1 design but Compose was selected for execution reproducibility [F-001].

## Question 15: What infrastructure additions would be required for a production deployment?
**Answer**: A production deployment requires: Kubernetes cluster management (EKS/GKE), an external managed PostgreSQL cluster (AWS RDS) with multi-AZ failover, managed RabbitMQ (Amazon MQ), HashiCorp Vault for secret management, and AWS CloudFront CDN for SPA static assets.

## Question 16: What is the purpose of the API Gateway, and why not let clients call microservices directly?
**Answer**: Direct client-to-microservice calls expose internal port numbers, force frontend clients to manage multiple CORS domains, and duplicate authentication verification across every service. The Gateway provides SSL termination, path routing, and central JWT security [F-003], [F-068].

## Question 17: How is distributed context tracing maintained across microservice calls?
**Answer**: Correlation IDs are maintained using the `X-Correlation-ID` header (`libs/common/ems_common/correlation.py:10`). The API Gateway generates a UUIDv4 header if missing, and microservice middleware forwards it across HTTP clients and AMQP message envelopes [F-032].

## Question 18: What strategy is used to prevent race conditions during leave approval?
**Answer**: Leave approvals execute atomic SQL `UPDATE` statements checking status `PENDING` (`services/leave/app/domain/leave.py:40`). If two managers attempt to approve the same leave simultaneously, the second update returns 0 rows modified and raises an HTTP 409 conflict [F-030].

## Question 19: How are database connection pools managed under high concurrency?
**Answer**: FastAPI microservices utilize SQLAlchemy 2.0 async engines configured with connection pool limits (`pool_size=10`, `max_overflow=20`, `pool_recycle=1800`) [F-019]. Redis caching offloads >80% of read queries, preventing connection pool exhaustion [F-022].

## Question 20: What happens if an outbox event fails to publish to RabbitMQ?
**Answer**: The outbox publisher retries publishing unacknowledged rows up to 3 times (`libs/common/ems_common/outbox.py:80`). If publication fails repeatedly, the outbox record is marked `FAILED` with error stack traces for administrator inspection [F-033].

## Question 21: How are frontend permissions validated, and can users bypass client-side guards?
**Answer**: Frontend UI hides write buttons and pages using permissions matrices (`frontend/src/lib/permissions.js:1`). Client-side checks are purely for user experience; security is strictly enforced at the API Gateway and backend microservice route handlers [F-028], [F-068].

## Question 22: How does the Notification service guarantee event delivery durability?
**Answer**: RabbitMQ queues are declared as `durable=True`, and messages are published with `delivery_mode=2` (persistent) [F-021]. If the Notification container crashes, unacknowledged messages remain safely queued in RabbitMQ until the container restarts [F-063].

## Question 23: What is the role of Prometheus and Grafana in your topology?
**Answer**: FastAPI microservices expose `/metrics` endpoints (`libs/common/ems_common/observability.py:1`). Prometheus scrapes metrics every 15 seconds [F-016], and Grafana visualizes HTTP request counts, p(95) latencies, DB connection counts, and RabbitMQ queue depth.

## Question 24: How long did the database event convergence take after heavy load testing?
**Answer**: After generating thousands of leave approval events under heavy load, outbox event processing and database state deltas converged completely within 3.37 seconds [F-059].

## Question 25: How does your CI/CD pipeline ensure software quality before deployment?
**Answer**: GitHub Actions executes a multi-job workflow on every push [F-067]: linting syntax, running 180 Pytest and 99 Vitest tests, auditing domain code coverage, building Docker images, and verifying live container stack health [F-047]–[F-053], [F-067].
