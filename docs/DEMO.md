# Employee Management System (EMS) - UI Demonstration Guide

This document provides a step-by-step demonstration walkthrough for evaluating the Employee Management System user interface (`frontend/src`), validating state transitions, role-based controls, and system workflows across supported roles (`ADMIN`, `HR`, `MANAGER`, `EMPLOYEE`) `[F-068]`.

---

## 1. Prerequisites & Environment Access

1. Ensure the full application stack is running in detached mode:
   ```bash
   docker compose up -d --wait
   ```
2. Open a web browser and navigate to the application URL:
   ```text
   http://localhost:8080
   ```
   *(Port `8080` published from Nginx container `[F-002]`)*.

3. **Authentication Setup**: The initial system administrator account is seeded automatically upon startup using environment variable settings `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.

---

## 2. Step-by-Step Demonstration Workflows

### Step 1: User Authentication & Role Dashboard (`/login` -> `/dashboard`)

1. **Navigate to Login**: Open `http://localhost:8080` in the browser. You are routed to `/login`.
2. **Enter Credentials**:
   - In the "Email Address" field (`#email`), enter the value of `ADMIN_EMAIL` (e.g. `admin@ems.com`).
   - In the "Password" field (`#password`), enter the value of `ADMIN_PASSWORD`.
3. **Submit**: Click the "Sign In" button.
4. **Expected Visible Result**:
   - The browser redirects to `/dashboard`.
   - The top header bar displays the user role badge `ADMIN` `[F-068]` alongside a "Logout" button.
   - The left sidebar displays navigation links for **Dashboard**, **Employees**, **Leave**, **Payroll**, **Notifications**, and **System**.
   - Dashboard summary cards display system-wide metrics: active employee headcount (`GET /employees`), pending leaves count (`GET /leaves`), and recent leave activity table.

---

### Step 2: Employee Onboarding Saga (`/employees`)

1. **Navigate to Directory**: Click **Employees** in the sidebar to navigate to `/employees`.
2. **Open Onboard Modal**: Click the "+ Onboard Employee" button (`data-testid="onboard-employee-btn"`).
3. **Fill Onboarding Form**:
   - **Full Name** (`#onboard-name`): Enter `John Doe`
   - **Email Address** (`#onboard-email`): Enter `john.doe@ems.com`
   - **Department** (`#onboard-dept`): Enter `Engineering`
   - **Designation** (`#onboard-desig`): Enter `Software Engineer`
   - **Reporting Manager** (`#onboard-manager`): Select `-- No Manager --` (or choose an active manager)
   - **System Role** (`#onboard-role`): Select `EMPLOYEE` `[F-068]`
   - **Initial Password** (`#onboard-pass`): Enter `Password123`
   - **Monthly Salary** (`#onboard-salary`): Enter `5000.00`
4. **Submit Form**: Click the "Submit Onboarding" button (`data-testid="submit-onboard-btn"`).
5. **Expected Visible Result**:
   - A loading indicator displays while the multi-service onboarding saga executes (`POST /employees` orchestrating Auth service `POST /internal/users` `[F-028]` and Payroll service `POST /internal/profiles` `[F-031]`).
   - A green notification toast appears reading: `"Employee onboarding initiated successfully!"`.
   - The modal closes, and the new employee record `John Doe` (`john.doe@ems.com`, Department: `Engineering`, Designation: `Software Engineer`) appears in the directory table with status badge `ACTIVE`.
   - An event `EmployeeOnboarded` `[F-034]` is written to the outbox and streamed via RabbitMQ topic exchange `ems.events` `[F-033]`.

---

### Step 3: Employee Leave Request Submission (`/leave`)

1. **Navigate to Leave Management**: Click **Leave** in the sidebar to navigate to `/leave`.
2. **Configure Request**:
   - **Employee Subject**: Select `John Doe` from the dropdown selector (or automatic selection if logged in as `EMPLOYEE`).
   - **Leave Type**: Select `PAID` (or `UNPAID`).
   - **Start Date**: Select a valid future weekday (e.g. `2026-10-12`).
   - **End Date**: Select a valid future weekday (e.g. `2026-10-14`).
   - **Reason**: Enter `Vacation trip`.
3. **Submit Request**: Click the "Submit Request" button.
4. **Expected Visible Result**:
   - Inline date logic validates that the range contains 3 business working days (excluding weekends) and does not exceed remaining paid allowance.
   - A green toast message appears reading: `"Leave request created successfully"`.
   - A new row appears in the Leave Requests table displaying Start Date `2026-10-12`, End Date `2026-10-14`, Days `3`, Leave Type `PAID`, and Status badge `PENDING`.
   - An outbox event `LeaveRequested` `[F-034]` is recorded in `leave_db` `[F-009]`.

---

### Step 4: Manager / HR Leave Decision (`/leave`)

1. **Locate Request**: On the `/leave` page, locate the pending request for `John Doe`.
2. **Approve Request**: In the Actions column of the request row, click the "Approve" button.
3. **Expected Visible Result**:
   - A database transaction locks the leave record (`SELECT ... FOR UPDATE`), verifies balance, updates status to `APPROVED`, and writes outbox event `LeaveApproved` `[F-034]`.
   - A green toast message appears reading: `"Leave request approved successfully"`.
   - The status badge in the table changes from `PENDING` to `APPROVED`.
   - The updated used leave days count reflects on the Leave Balance card.

---

### Step 5: Monthly Payroll Run Execution (`/payroll`)

1. **Navigate to Payroll**: Click **Payroll** in the sidebar to navigate to `/payroll`.
2. **Configure Run**: On the "Run Payroll" card (accessible to `HR` and `ADMIN` roles `[F-068]`):
   - **Select Month**: Enter target month in format `YYYY-MM` (e.g. `2026-10`).
   - Click the "Run Payroll for Month" button.
3. **Confirm Action**: A confirmation modal dialog appears titled "Confirm Payroll Processing". Click "Run Payroll".
4. **Expected Visible Result**:
   - The endpoint `POST /payroll/run?month=2026-10` `[F-031]` processes all active payroll profiles, applying unpaid leave deduction algorithms.
   - A summary banner displays: `"Payroll run complete. Created X payslips, Skipped Y existing profiles."`.
   - In the Payslip Breakdown table below, selecting `John Doe` displays their payslip record with Gross Salary, Unpaid Leave Days, Deductions, and Net Salary formatted via `formatMoney`.

---

### Step 6: Asynchronous Event Notification Verification (`/notifications`)

1. **Navigate to Notifications**: Click **Notifications** in the sidebar to navigate to `/notifications`.
2. **Filter & Refresh**: Select subject `John Doe` (if `ADMIN` / `HR`) or view default feed. Set limit dropdown to `50`. Click "Refresh".
3. **Expected Visible Result**:
   - The list displays real-time event notifications consumed from RabbitMQ topic exchange `ems.events` `[F-033]`, ordered newest first:
     - `EmployeeOnboarded`: `"Welcome John Doe, your account is ready."`
     - `LeaveRequested`: `"Your PAID leave from 2026-10-12 to 2026-10-14 (3 days) was requested."`
     - `LeaveApproved`: `"Your PAID leave from 2026-10-12 to 2026-10-14 (3 days) was approved."`
   - Each notification displays an event type badge, message body, and ISO creation timestamp.

---

### Step 7: System Health & Infrastructure Monitoring (`/system`)

1. **Navigate to System**: Click **System** in the sidebar to navigate to `/system` (accessible to `HR` and `ADMIN` roles `[F-068]`).
2. **Execute Health Checks**: Click the "Check now" button.
3. **Expected Visible Result**:
   - The page performs non-blocking `fetch` checks with 5-second timeouts against service endpoints.
   - Service status cards render green `UP` status badges and response latency in milliseconds for:
     - Auth Service (`:8001` `[F-004]`)
     - Employee Service (`:8002` `[F-006]`)
     - Leave Service (`:8003` `[F-008]`)
     - Payroll Service (`:8004` `[F-010]`)
     - Notification Service (`:8005` `[F-012]`)
     - API Gateway (`:8000` `[F-003]`)
   - Infrastructure Monitoring links are displayed opening in new tabs:
     - **Grafana Telemetry**: `http://localhost:3000`
     - **Prometheus Server**: `http://localhost:9090` `[F-016]`
     - **RabbitMQ Management**: `http://localhost:15672` `[F-014]`
