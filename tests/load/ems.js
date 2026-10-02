import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';


const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:8000';
const ADMIN_EMAIL = __ENV.ADMIN_EMAIL;
const ADMIN_PASSWORD = __ENV.ADMIN_PASSWORD;

if (!ADMIN_EMAIL || !ADMIN_PASSWORD) {
  throw new Error('Missing ADMIN_EMAIL or ADMIN_PASSWORD in __ENV.');
}

const READ_MAX_VUS = parseInt(__ENV.READ_MAX_VUS || '30', 10);
const LEAVE_MAX_VUS = parseInt(__ENV.LEAVE_MAX_VUS || '15', 10);
const ONBOARD_RATE = parseInt(__ENV.ONBOARD_RATE || '2', 10);

export const options = {
  setupTimeout: '180s',
  scenarios: {
    reads: {
      executor: 'ramping-vus',
      exec: 'scenarioReads',
      startTime: '0s',
      stages: [
        { duration: '30s', target: Math.floor(READ_MAX_VUS / 3) },
        { duration: '60s', target: READ_MAX_VUS },
        { duration: '30s', target: 0 },
      ],
    },
    leave_flow: {
      executor: 'ramping-vus',
      exec: 'scenarioLeaveFlow',
      startTime: '2m10s',
      stages: [
        { duration: '30s', target: Math.floor(LEAVE_MAX_VUS / 3) },
        { duration: '60s', target: LEAVE_MAX_VUS },
        { duration: '20s', target: 0 },
      ],
    },
    onboarding: {
      executor: 'constant-arrival-rate',
      exec: 'scenarioOnboarding',
      startTime: '3m45s',
      duration: '60s',
      rate: ONBOARD_RATE,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 30,
    },
  },
  thresholds: {
    'http_req_duration{name:create_leave}': ['p(95)<1000'],
    'http_req_duration{name:approve_leave}': ['p(95)<1000'],
    'http_req_duration{name:onboard_employee}': ['p(95)<3000'],
    'http_req_duration{scenario:reads}': ['p(95)<500'],
    'http_req_failed{scenario:reads}': ['rate<0.01'],
    'http_req_failed{scenario:leave_flow}': ['rate<0.01'],
    'http_req_failed{scenario:onboarding}': ['rate<0.01'],
    'checks': ['rate>0.99'],
  },
};

export function setup() {
  // 1. Login Admin
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  if (loginRes.status !== 200) {
    throw new Error(`Admin login failed in setup: ${loginRes.status} ${loginRes.body}`);
  }

  const adminToken = loginRes.json('access_token');
  const runId = Date.now();
  const employees = [];

  // 2. Create LEAVE_MAX_VUS employees
  for (let i = 0; i < LEAVE_MAX_VUS; i++) {
    const email = `load.emp.${runId}.${i}@test.com`;
    const password = 'Password123!';
    const empPayload = {
      name: `Load User ${i}`,
      email: email,
      department: `load-${runId}`,
      designation: 'Engineer',
      initial_password: password,
      monthly_salary: 30000.0,
      role: 'EMPLOYEE',
    };

    const empRes = http.post(
      `${BASE_URL}/employees`,
      JSON.stringify(empPayload),
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${adminToken}`,
        },
      }
    );

    if (empRes.status !== 201) {
      throw new Error(`Employee creation failed in setup for index ${i}: ${empRes.status} ${empRes.body}`);
    }

    const empId = empRes.json('id');

    // Login employee to get user token
    const userLoginRes = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email: email, password: password }),
      { headers: { 'Content-Type': 'application/json' } }
    );

    if (userLoginRes.status !== 200) {
      throw new Error(`Employee login failed in setup for index ${i}: ${userLoginRes.status} ${userLoginRes.body}`);
    }

    const userToken = userLoginRes.json('access_token');
    employees.push({ id: empId, token: userToken });
  }

  return { adminToken, employees, runId };
}

export function scenarioReads(data) {
  const empIndex = exec.scenario.iterationInInstance % data.employees.length;
  const emp = data.employees[empIndex];

  const params = {
    headers: { Authorization: `Bearer ${data.adminToken}` },
  };

  const resList = http.get(`${BASE_URL}/employees?page=1&page_size=20`, params);
  check(resList, { 'GET /employees status 200': (r) => r.status === 200 });

  const resDetail = http.get(`${BASE_URL}/employees/${emp.id}`, params);
  check(resDetail, { 'GET /employees/{id} status 200': (r) => r.status === 200 });

  sleep(Math.random() * 1.0 + 0.5);
}

function getNthWeekdayFrom2100(n) {
  // Count n weekdays (Mon-Fri) starting from 2100-01-03
  let current = new Date(Date.UTC(2100, 0, 3)); // 2100-01-03
  let weekdaysFound = 0;

  while (weekdaysFound < n) {
    current.setUTCDate(current.getUTCDate() + 1);
    const dayOfWeek = current.getUTCDay(); // 0 is Sun, 6 is Sat
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      weekdaysFound++;
    }
  }

  const yyyy = current.getUTCFullYear();
  const mm = String(current.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(current.getUTCDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export function scenarioLeaveFlow(data) {
  const vuIndex = exec.vu.idInInstance - 1;
  const emp = data.employees[vuIndex % data.employees.length];

  const n = exec.scenario.iterationInInstance + 1;
  const leaveDate = getNthWeekdayFrom2100(n);

  // 1. POST /leaves as employee
  const createRes = http.post(
    `${BASE_URL}/leaves`,
    JSON.stringify({
      employee_id: emp.id,
      start_date: leaveDate,
      end_date: leaveDate,
      leave_type: 'UNPAID',
      reason: 'k6 load test leave',
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${emp.token}`,
      },
      tags: { name: 'create_leave' },
    }
  );

  const createOk = check(createRes, {
    'create_leave status 201': (r) => r.status === 201,
    'create_leave has id': (r) => r.json('id') !== undefined,
  });

  if (!createOk || createRes.status !== 201) {
    return;
  }

  const leaveId = createRes.json('id');

  // 2. POST /leaves/{id}/approve as admin
  const approveRes = http.post(
    `${BASE_URL}/leaves/${leaveId}/approve`,
    null,
    {
      headers: { Authorization: `Bearer ${data.adminToken}` },
      tags: { name: 'approve_leave' },
    }
  );

  check(approveRes, {
    'approve_leave status 200': (r) => r.status === 200,
    'approve_leave is APPROVED': (r) => r.json('status') === 'APPROVED',
  });

  // 3. GET /leaves/balance/{employee_id} as employee
  const balanceRes = http.get(
    `${BASE_URL}/leaves/balance/${emp.id}?year=2100`,
    {
      headers: { Authorization: `Bearer ${emp.token}` },
      tags: { name: 'balance' },
    }
  );

  check(balanceRes, {
    'balance status 200': (r) => r.status === 200,
  });
}

export function scenarioOnboarding(data) {
  const uniqueEmail = `load.onboard.${data.runId}.${exec.vu.idInInstance}.${exec.scenario.iterationInInstance}@test.com`;
  const dept = `load-dept-${data.runId}-${exec.vu.idInInstance}`;

  const onboardRes = http.post(
    `${BASE_URL}/employees`,
    JSON.stringify({
      name: `Onboard User ${exec.scenario.iterationInInstance}`,
      email: uniqueEmail,
      department: dept,
      designation: 'Load Tester',
      initial_password: 'Password123!',
      monthly_salary: 35000.0,
      role: 'EMPLOYEE',
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${data.adminToken}`,
      },
      tags: { name: 'onboard_employee' },
    }
  );

  check(onboardRes, {
    'onboard_employee status 201': (r) => r.status === 201,
    'onboard_employee is ACTIVE': (r) => r.json('status') === 'ACTIVE',
  });
}

export function handleSummary(data) {
  return {
    '/scripts/results/summary.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data),
  };
}

function textSummary(data) {
  let output = '\n==================== K6 LOAD TEST SUMMARY ====================\n';
  const metrics = data.metrics || {};

  for (const [key, metric] of Object.entries(metrics)) {
    if (metric.values) {
      const v = metric.values;
      const count = v.count !== undefined ? v.count : '-';
      const rate = v.rate !== undefined ? (v.rate * 100).toFixed(2) + '%' : '-';
      const avg = v.avg !== undefined ? v.avg.toFixed(2) + 'ms' : '-';
      const p90 = v['p(90)'] !== undefined ? v['p(90)'].toFixed(2) + 'ms' : '-';
      const p95 = v['p(95)'] !== undefined ? v['p(95)'].toFixed(2) + 'ms' : '-';
      output += `${key.padEnd(45)} | count: ${String(count).padEnd(6)} | avg: ${avg.padEnd(9)} | p(90): ${p90.padEnd(9)} | p(95): ${p95.padEnd(9)} | rate: ${rate}\n`;
    }
  }

  output += '==============================================================\n';
  return output;
}
