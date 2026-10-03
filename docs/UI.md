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
├── nginx.conf              # SPA fallback, /api/ reverse proxy, /status/* proxies
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
    │   ├── dates.js        # UTC-based date arithmetic (countWeekdays, validateLeaveRange)
    │   ├── employeeRules.js# Client validation for employee onboard/edit forms
    │   ├── jwt.js          # Base64URL JWT payload decoder & expiration check
    │   ├── leaveRules.js   # Leave action permission rules & target employee checks
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
    │   ├── Employees.jsx   # Employee directory, onboard saga modal, edit & soft-delete
    │   ├── Leave.jsx       # Leave management, balance card, request form, decision tabs
    │   ├── Login.jsx       # Authentication form page
    │   └── PlaceholderPages.jsx # Dashboard, Payroll, Notifications, System, NotAllowed
    └── test/
        ├── setup.js            # Vitest setup & testing-library matchers
        ├── api.test.js         # API wrapper unit tests
        ├── dates.test.js       # Date logic unit tests (weekdays, leap year, ranges)
        ├── employeeRules.test.js# Employee validation unit tests
        ├── employeesPage.test.jsx# Employees page component tests (onboard, 502 saga, submit lock)
        ├── jwt.test.js         # JWT decode & expiration unit tests
        ├── leavePage.test.jsx  # Leave page component tests (ADMIN subject, weekend block, 409 toast)
        ├── leaveRules.test.js  # Leave permissions & action matrix unit tests
        ├── login.test.jsx      # Login page component tests
        ├── permissions.test.js # Permission matrix coverage tests
        └── router.test.jsx     # Route guard & protection integration tests
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

### Employees Screen (`/employees`)
- **Role Access**: `ADMIN` and `HR` have full write access (Onboard, Edit, Soft Delete). `MANAGER` has read-only access (table and details modal, no write buttons).
- **Filtering**:
  - **Department Filter**: Server-side parameter (`GET /employees?department=...`). Dropdown options dynamically built from loaded data with free-text fallback.
  - **"Filter this page"**: Client-side text input clearly labeled as filtering only currently loaded page rows by name or email.
- **Onboarding & Saga Failure**:
  - Submitting onboard form displays `"Onboarding in progress: creating account and payroll profile"`.
  - Submit button disabled while request is running to prevent duplicate submissions.
  - On HTTP `502` with code `ONBOARDING_FAILED`: displays a persistent error panel explaining that onboarding steps were rolled back, a record with status `ONBOARDING_FAILED` now exists in DB, and the email remains reserved.

### Leave Management Screen (`/leave`)
- **100-Employee Limit**: Name resolution and employee selector dropdowns query `GET /employees?page_size=100` once on page load. Employee IDs are mapped to names; if an ID is not in the top 100 list, the UI falls back to displaying the first 8 characters of the UUID.
- **Leave Balance Summary**:
  - Displays allowance, used, and remaining days with a progress bar (`GET /leaves/balance/{employee_id}?year=YYYY`).
  - Subject selector: `EMPLOYEE` and `MANAGER` are fixed to their own user ID. `HR` and `ADMIN` can select any employee (seeded `ADMIN` user is not an employee record, so `ADMIN` has no default subject and must select one).
- **Leave Request Form**:
  - Validates date range inline before submit using `countWeekdays` (Mon-Fri) and `validateLeaveRange` (blocks cross-year ranges, end < start, and 0-weekday weekend-only requests).
  - Submit button disabled while request is in progress.
- **Decision Tabs & Actions**:
  - Tabs available for `MANAGER`, `HR`, `ADMIN`: **All Visible** and **Needs My Decision** (client-side filtered view of `PENDING` leaves where user has approval rights).
  - Action buttons (`Approve`, `Reject`, `Cancel`) render strictly according to `leaveActions` rules (`MANAGER` cannot approve own leave; `MANAGER` can only approve leaves where `manager_id == user.id`). `Reject` and `Cancel` prompt confirmation via `ConfirmDialog`.

---

## Technical Constraints & Design Rules

1. **No Polling & No Auto-Refresh**: No background timers or automated polling timers exist in the frontend. API requests are triggered strictly by explicit user actions (e.g. form submission, page navigation, tab selection, or manual filter entry) to protect the shared Nginx IP gateway rate limit.
2. **Nginx IP Gateway Rate Limit**: The API Gateway enforces fixed-window rate limits keyed by client IP (`request.client.host`). Because all frontend browser requests pass through the Nginx container proxying to `gateway:8000`, the Gateway sees Nginx's IP for all incoming traffic. This shares the global limit of 100 requests/minute and 10 login requests/minute across all browser sessions.
