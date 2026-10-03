# EMS Frontend Specification & Documentation

## Stack

- **Framework**: React 18 + Vite (Plain JavaScript)
- **Routing**: `react-router-dom` (SPA with protected route guards)
- **Styling**: Vanilla CSS with custom CSS variables (dark theme palette)
- **Testing**: `vitest` + `@testing-library/react` + `jsdom`
- **Server / Container**: Multi-stage Docker build (Node 22 LTS -> Nginx Alpine)

---

## How to Run

1. Start full stack including frontend:
   ```bash
   docker compose up -d --wait
   ```
2. Access the application UI in browser:
   ```text
   http://localhost:8080
   ```

---

## Folder Layout

```text
frontend/
├── Dockerfile              # Multi-stage build (Node build -> Nginx serve)
├── nginx.conf              # SPA fallback, /api/ reverse proxy, /status/* proxies with dynamic Docker DNS resolver (127.0.0.11)
├── package.json            # Dependencies & scripts
├── package-lock.json       # Pinned dependency locks
├── vite.config.js          # Vite & Vitest configuration
├── index.html              # HTML entrypoint
└── src/
    ├── main.jsx            # React root DOM rendering
    ├── App.jsx             # Router layout & protected route shell
    ├── index.css           # Global design system & utility classes
    ├── lib/
    │   ├── api.js          # Fetch wrapper (/api base, error mapping, 401 redirect)
    │   ├── config.js       # Development port constants (3000, 9090, 15672) & monitoring tool URLs
    │   ├── dates.js        # UTC-based date arithmetic (countWeekdays, validateLeaveRange)
    │   ├── employeeRules.js# Client validation for employee onboard/edit forms
    │   ├── jwt.js          # Base64URL JWT payload decoder & expiration check
    │   ├── leaveRules.js   # Leave action permission rules & target employee checks
    │   ├── money.js        # Currency formatting utility (formatMoney string & decimal formatter)
    │   ├── permissions.js  # Role-based route and action permission matrix
    │   └── session.js      # Session storage token manager & auto-logout timer
    ├── components/
    │   ├── Badge.jsx       # Status and role badge indicator
    │   ├── ConfirmDialog.jsx# Modal confirmation dialog for destructive actions
    │   ├── DataTable.jsx   # Data table component with loading state and empty fallback
    │   ├── EmptyState.jsx  # Empty state graphic readout
    │   ├── FormField.jsx   # Form input label, required marker, inline error wrapper
    │   ├── Modal.jsx       # Popup modal wrapper
    │   ├── Pagination.jsx  # Table pagination controls and page size selector
    │   ├── Sidebar.jsx     # Navigation sidebar (filtered by role permissions)
    │   ├── Spinner.jsx     # Loading spinner indicator
    │   ├── Toast.jsx       # Alert toast messages (error / success)
    │   └── TopBar.jsx      # Header bar displaying role and logout button
    ├── pages/
    │   ├── Dashboard.jsx   # Role-specific dashboard (request budget <= 6)
    │   ├── Employees.jsx   # Employee directory, onboard saga modal, edit & soft-delete
    │   ├── Leave.jsx       # Leave management, balance card, request form, decision tabs
    │   ├── Login.jsx       # Authentication form page
    │   ├── Notifications.jsx # Event notifications list, limit selector, refresh button
    │   ├── Payroll.jsx     # Batch payroll run card (HR/ADMIN) & payslip breakdown viewer
    │   ├── PlaceholderPages.jsx # NotAllowed fallback page
    │   └── System.jsx      # Service status checks & telemetry links (HR/ADMIN)
    └── test/
        ├── setup.js            # Vitest setup & testing-library matchers
        ├── api.test.js         # API wrapper unit tests
        ├── dashboardPage.test.jsx# Dashboard component tests (roles, request budget, isolated card errors)
        ├── dates.test.js       # Date logic unit tests (weekdays, leap year, ranges)
        ├── employeeRules.test.js# Employee validation unit tests
        ├── employeesPage.test.jsx# Employees page component tests (onboard, 502 saga, submit lock)
        ├── jwt.test.js         # JWT decode & expiration unit tests
        ├── leavePage.test.jsx  # Leave page component tests (ADMIN subject, weekend block, 409 toast)
        ├── leaveRules.test.js  # Leave permissions & action matrix unit tests
        ├── login.test.jsx      # Login page component tests
        ├── money.test.js       # Money formatting unit tests
        ├── notificationsPage.test.jsx # Notifications page component tests (limit param, refresh)
        ├── payrollPage.test.jsx# Payroll page component tests (run card, confirm dialog, 422 error)
        ├── permissions.test.js # Permission matrix coverage tests
        ├── router.test.jsx     # Route guard & protection integration tests
        └── systemPage.test.jsx # System page component tests (UP/DOWN/timeout mapping, timer checks)
```

---

## Permission & Action Matrix

| Role | Accessible Routes | Allowed Actions |
| :--- | :--- | :--- |
| `ADMIN` | `/dashboard`, `/employees`, `/leave`, `/payroll`, `/notifications`, `/system` | `employee.write` (Onboard, Edit, Soft Delete), `leave.decide` (Approve, Reject, Cancel), `payroll.run` |
| `HR` | `/dashboard`, `/employees`, `/leave`, `/payroll`, `/notifications`, `/system` | `employee.write` (Onboard, Edit, Soft Delete), `leave.decide` (Approve, Reject, Cancel), `payroll.run` |
| `MANAGER` | `/dashboard`, `/employees` (read-only), `/leave`, `/payroll` (own payslips), `/notifications` | `leave.decide` (Approve/Reject leaves assigned to manager ID; Cancel own leaves) |
| `EMPLOYEE` | `/dashboard`, `/leave` (own), `/payroll` (own payslips), `/notifications` | Request own leave; Cancel own pending/approved leave |

---

## Screen Specifications & Features

### Dashboard Screen (`/dashboard`)
- **Request Budget**: Strict budget of at most 6 API requests per page load across all roles.
- **Role Layouts**:
  - `EMPLOYEE`: Leave balance card (`GET /leaves/balance/{me}`), My pending requests count (`GET /leaves?status=PENDING&page_size=1`), Latest 5 notifications (`GET /notifications/{me}?limit=5`).
  - `MANAGER`: All `EMPLOYEE` cards plus "Leaves awaiting my decision" table (`GET /leaves?status=PENDING&page_size=100`, filtered client-side with `leaveActions(user, row).canApprove`, labeled "among the first 100").
  - `HR` & `ADMIN`: Active headcount (`GET /employees?page_size=1`), System pending leaves count (`GET /leaves?status=PENDING&page_size=1`), 5 most recent leave requests table (`GET /leaves?page=1&page_size=5` and `GET /employees?page_size=100` for name resolution), Quick action buttons to Employees, Leave, Payroll.
  - **ADMIN User**: Seeded `ADMIN` user has no employee record; personal cards (balance, notifications) are completely hidden for `ADMIN`.
- **Card Error Isolation**: Each card maintains independent loading and error state so a single API failure does not blank out other cards.

### Employees Screen (`/employees`)
- **Role Access**: `ADMIN` and `HR` have full write access (Onboard, Edit, Soft Delete). `MANAGER` has read-only access.
- **Filtering**: Server-side department filter (`GET /employees?department=...`) and client-side "Filter this page" text box for loaded rows.
- **Onboard Saga Error**: Displays persistent `ONBOARDING_FAILED` panel on HTTP `502` explaining rollback, email reservation, and DB record status.

### Leave Management Screen (`/leave`)
- **100-Employee Limit**: Employee selector dropdowns and name resolution map query `GET /employees?page_size=100` once at page load. Fallback to first 8 characters of UUID if not found in map.
- **Subject Selector**: `EMPLOYEE` and `MANAGER` are fixed to self. `HR` and `ADMIN` can select any employee (seeded `ADMIN` has no default subject).
- **Date Validation**: Validates date range inline before submit using `countWeekdays` (Mon-Fri) and `validateLeaveRange` (blocks cross-year ranges, end < start, and 0-weekday weekend-only requests).

### Payroll & Payslips Screen (`/payroll`)
- **Run Payroll Card (`HR` and `ADMIN` only)**:
  - Target month input (`YYYY-MM`). Malformed month is blocked client-side without sending an API request.
  - Warns (without blocking) if target month is in the future.
  - Confirmation dialog required before `POST /payroll/run?month=YYYY-MM`. Submit button disabled while request is running.
  - Displays summary on completion: `Created X payslips, Skipped Y existing profiles`. Handles HTTP `422` error messages.
- **Payslip Viewer**:
  - `EMPLOYEE` and `MANAGER`: Fixed to own subject (`user.id`).
  - `HR` and `ADMIN`: Employee subject selector (`GET /employees?page_size=100`).
  - Table shows Month, Gross Salary, Unpaid Leave Days, Deductions, Net Salary, and Created Date. Values formatted using `formatMoney`.
  - Row click opens breakdown modal displaying API values and the contract rule: `"deduction = gross salary / working days in the month x unpaid leave days"`, with working days computed via `countWeekdays` for that month (labeled "computed from the contract rule").

### Notifications Screen (`/notifications`)
- **Subject Selection**: `EMPLOYEE` and `MANAGER` fixed to self; `HR` and `ADMIN` select employee subject via dropdown.
- **Controls**: Limit selector (`50`, `100`, `200`) and explicit **Refresh** button.
- **List Display**: Displays newest notifications first with event type badge (`EmployeeOnboarded`, `LeaveRequested`, `LeaveApproved`, `LeaveRejected`, `LeaveCancelled`), message text, and formatted timestamp. Displays `EmptyState` when list is empty.

### System Health & Telemetry Screen (`/system`)
- **Role Access**: Restricted to `HR` and `ADMIN`.
- **Health Checks**: Calls unauthenticated Nginx routes (`/status/auth`, `/status/employee`, `/status/leave`, `/status/payroll`, `/status/notification`, `/status/gateway`) using standard `fetch` with an `AbortController` 5-second timeout.
- **Status Mapping**: Displays `UP` for HTTP 200 responses and `DOWN` for any other status code or timeout/network error, alongside response time in milliseconds. Includes a "Check now" button for manual execution.
- **Infrastructure Monitoring Links**: Renders links to Grafana, Prometheus, and RabbitMQ Management UI built via `lib/config.js` from `window.location.hostname` and local development default ports (`3000`, `9090`, `15672`). Links open in a new tab with `rel="noopener noreferrer"`.

---

## Technical Constraints & Design Rules

1. **No Polling & No Auto-Refresh**: No background timers or automated polling timers exist in the frontend. API requests are triggered strictly by explicit user actions (e.g. form submission, page navigation, tab selection, or manual filter/refresh entry) to protect the shared Nginx IP gateway rate limit.
2. **Nginx IP Gateway Rate Limit**: The API Gateway enforces fixed-window rate limits keyed by client IP (`request.client.host`). Because all frontend browser requests pass through the Nginx container proxying to `gateway:8000`, the Gateway sees Nginx's IP for all incoming traffic. This shares the global limit of 100 requests/minute and 10 login requests/minute across all browser sessions.
3. **Development Default Telemetry Ports**: Local infrastructure telemetry links use default development ports: Grafana (`:3000`), Prometheus (`:9090`), and RabbitMQ Management (`:15672`).
