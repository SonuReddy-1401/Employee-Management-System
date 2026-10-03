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
    │   ├── jwt.js          # Base64URL JWT payload decoder & expiration check
    │   ├── permissions.js  # Role-based route and action permission matrix
    │   └── session.js      # Session storage token manager & auto-logout timer
    ├── components/
    │   ├── Badge.jsx       # Status and role badge indicator
    │   ├── Sidebar.jsx     # Navigation sidebar (filtered by role permissions)
    │   ├── Spinner.jsx     # Loading spinner indicator
    │   ├── Toast.jsx       # Alert toast messages (error / success)
    │   └── TopBar.jsx      # Header bar displaying role and logout button
    ├── pages/
    │   ├── Login.jsx       # Authentication form page
    │   └── PlaceholderPages.jsx # Dashboard, Employees, Leave, Payroll, Notifications, System, NotAllowed
    └── test/
        ├── setup.js        # Vitest setup & testing-library matchers
        ├── api.test.js     # API wrapper unit tests
        ├── jwt.test.js     # JWT decode & expiration unit tests
        ├── login.test.jsx  # Login page component tests
        ├── permissions.test.js # Permission matrix coverage tests
        └── router.test.jsx # Route guard & protection integration tests
```

---

## Permission Matrix

| Role | Accessible Routes | Allowed Actions |
| :--- | :--- | :--- |
| `ADMIN` | `/dashboard`, `/employees`, `/leave`, `/payroll`, `/notifications`, `/system` | `employee.write`, `leave.decide`, `payroll.run` |
| `HR` | `/dashboard`, `/employees`, `/leave`, `/payroll`, `/notifications`, `/system` | `employee.write`, `leave.decide`, `payroll.run` |
| `MANAGER` | `/dashboard`, `/employees` (read-only), `/leave`, `/payroll` (own payslips), `/notifications` | `leave.decide` |
| `EMPLOYEE` | `/dashboard`, `/leave` (own), `/payroll` (own payslips), `/notifications` | *(None)* |

---

## Known Limitations

- **Gateway Rate Limiting**: The API Gateway enforces fixed-window rate limits keyed by client IP (`request.client.host`). Because all frontend browser requests pass through the Nginx container proxying to `gateway:8000`, the Gateway sees Nginx's IP for all incoming traffic. This shares the global limit of 100 requests/minute and 10 login requests/minute across all browser sessions. Frontend polling must not be configured faster than every 30 seconds to avoid HTTP 429 rate limit errors.
