import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api.js';
import { leaveActions } from '../lib/leaveRules.js';
import { ROLES } from '../lib/permissions.js';
import { Badge } from '../components/Badge.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Dashboard({ user }) {
  const role = user?.role;
  const isAdmin = role === ROLES.ADMIN;
  const isHR = role === ROLES.HR;
  const isManager = role === ROLES.MANAGER;
  const isEmployee = role === ROLES.EMPLOYEE;

  // Independent card states
  const [balance, setBalance] = useState({ loading: false, data: null, error: null });
  const [myPendingCount, setMyPendingCount] = useState({ loading: false, count: 0, error: null });
  const [notifications, setNotifications] = useState({ loading: false, items: [], error: null });
  const [managerDecisionLeaves, setManagerDecisionLeaves] = useState({ loading: false, items: [], error: null });

  // HR & ADMIN card states
  const [headcount, setHeadcount] = useState({ loading: false, count: 0, error: null });
  const [totalPendingLeaves, setTotalPendingLeaves] = useState({ loading: false, count: 0, error: null });
  const [recentLeaves, setRecentLeaves] = useState({ loading: false, items: [], employeeMap: {}, error: null });

  // Fetch EMPLOYEE & MANAGER data (Balance, My Pending, Notifications)
  useEffect(() => {
    if ((isEmployee || isManager) && user?.id) {
      // 1. Leave Balance
      setBalance({ loading: true, data: null, error: null });
      const currentYear = new Date().getUTCFullYear();
      api.get(`/leaves/balance/${user.id}?year=${currentYear}`)
        .then((data) => setBalance({ loading: false, data, error: null }))
        .catch((err) => setBalance({ loading: false, data: null, error: err.message }));

      // 2. My Pending Leaves count
      setMyPendingCount({ loading: true, count: 0, error: null });
      api.get('/leaves?status=PENDING&page_size=1')
        .then((res) => setMyPendingCount({ loading: false, count: res?.total || 0, error: null }))
        .catch((err) => setMyPendingCount({ loading: false, count: 0, error: err.message }));

      // 3. Notifications (latest 5)
      setNotifications({ loading: true, items: [], error: null });
      api.get(`/notifications/${user.id}?limit=5`)
        .then((items) => setNotifications({ loading: false, items: items || [], error: null }))
        .catch((err) => setNotifications({ loading: false, items: [], error: err.message }));
    }

    // 4. MANAGER "Awaiting my decision" leaves
    if (isManager && user?.id) {
      setManagerDecisionLeaves({ loading: true, items: [], error: null });
      api.get('/leaves?status=PENDING&page_size=100')
        .then((res) => {
          const raw = res?.items || [];
          const filtered = raw.filter((item) => leaveActions(user, item).canApprove);
          setManagerDecisionLeaves({ loading: false, items: filtered, error: null });
        })
        .catch((err) => setManagerDecisionLeaves({ loading: false, items: [], error: err.message }));
    }
  }, [isAdmin, isManager, user]);

  // Fetch HR & ADMIN data (Headcount, Total Pending, Recent Leaves with Employee Map)
  useEffect(() => {
    if (isAdmin || isHR) {
      // 1. Headcount (excludes deleted)
      setHeadcount({ loading: true, count: 0, error: null });
      api.get('/employees?page_size=1')
        .then((res) => setHeadcount({ loading: false, count: res?.total || 0, error: null }))
        .catch((err) => setHeadcount({ loading: false, count: 0, error: err.message }));

      // 2. Total Pending Leaves
      setTotalPendingLeaves({ loading: true, count: 0, error: null });
      api.get('/leaves?status=PENDING&page_size=1')
        .then((res) => setTotalPendingLeaves({ loading: false, count: res?.total || 0, error: null }))
        .catch((err) => setTotalPendingLeaves({ loading: false, count: 0, error: err.message }));

      // 3. 5 Most Recent Leaves & Employee Name Map
      setRecentLeaves({ loading: true, items: [], employeeMap: {}, error: null });
      Promise.all([
        api.get('/leaves?page=1&page_size=5'),
        api.get('/employees?page_size=100'),
      ])
        .then(([leavesRes, empRes]) => {
          const empMap = {};
          if (empRes && empRes.items) {
            empRes.items.forEach((e) => {
              empMap[e.id] = e.name;
            });
          }
          setRecentLeaves({
            loading: false,
            items: leavesRes?.items || [],
            employeeMap: empMap,
            error: null,
          });
        })
        .catch((err) => setRecentLeaves({ loading: false, items: [], employeeMap: {}, error: err.message }));
    }
  }, [isAdmin, isHR]);

  const resolveName = (empId, map) => {
    if (!empId) return '—';
    return map[empId] || empId.slice(0, 8);
  };

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="card-title" style={{ margin: 0 }}>
          Dashboard Overview
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Welcome back! Here is your role-specific overview.
        </p>
      </div>

      {/* HR & ADMIN Quick Actions */}
      {(isAdmin || isHR) && (
        <div className="card" style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Quick Actions:</strong>
          <Link to="/employees" className="btn btn-primary" style={{ textDecoration: 'none', padding: '0.375rem 0.75rem', fontSize: '0.875rem' }}>
            Employees Directory
          </Link>
          <Link to="/leave" className="btn btn-secondary" style={{ textDecoration: 'none', padding: '0.375rem 0.75rem', fontSize: '0.875rem' }}>
            Leave Management
          </Link>
          <Link to="/payroll" className="btn btn-secondary" style={{ textDecoration: 'none', padding: '0.375rem 0.75rem', fontSize: '0.875rem' }}>
            Payroll
          </Link>
        </div>
      )}

      {/* Grid Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Headcount Card (HR / ADMIN) */}
        {(isAdmin || isHR) && (
          <div className="card" data-testid="headcount-card">
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Active Headcount
            </div>
            {headcount.loading ? (
              <Spinner />
            ) : headcount.error ? (
              <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{headcount.error}</div>
            ) : (
              <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {headcount.count}
              </div>
            )}
          </div>
        )}

        {/* Total Pending Leaves Card (HR / ADMIN) */}
        {(isAdmin || isHR) && (
          <div className="card" data-testid="total-pending-leaves-card">
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              System Pending Leaves
            </div>
            {totalPendingLeaves.loading ? (
              <Spinner />
            ) : totalPendingLeaves.error ? (
              <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{totalPendingLeaves.error}</div>
            ) : (
              <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-warning)' }}>
                {totalPendingLeaves.count}
              </div>
            )}
          </div>
        )}

        {/* Leave Balance Card (EMPLOYEE, MANAGER) */}
        {(isEmployee || isManager) && (
          <div className="card" data-testid="leave-balance-card">
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              My Leave Balance ({new Date().getUTCFullYear()})
            </div>
            {balance.loading ? (
              <Spinner />
            ) : balance.error ? (
              <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{balance.error}</div>
            ) : balance.data ? (
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-success)' }}>
                  {balance.data.remaining} days remaining
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Used: {balance.data.used} / Allowance: {balance.data.allowance}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* My Pending Leaves Count (EMPLOYEE, MANAGER) */}
        {(isEmployee || isManager) && (
          <div className="card" data-testid="my-pending-leaves-card">
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              My Pending Requests
            </div>
            {myPendingCount.loading ? (
              <Spinner />
            ) : myPendingCount.error ? (
              <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{myPendingCount.error}</div>
            ) : (
              <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                {myPendingCount.count}
              </div>
            )}
          </div>
        )}
      </div>

      {/* HR & ADMIN Recent Leaves Table */}
      {(isAdmin || isHR) && (
        <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="recent-leaves-card">
          <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '1rem' }}>
            5 Most Recent Leave Requests
          </h2>
          {recentLeaves.loading ? (
            <Spinner />
          ) : recentLeaves.error ? (
            <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{recentLeaves.error}</div>
          ) : recentLeaves.items.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No leave requests found.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Dates</th>
                  <th>Type</th>
                  <th>Days</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentLeaves.items.map((item) => (
                  <tr key={item.id}>
                    <td>{resolveName(item.employee_id, recentLeaves.employeeMap)}</td>
                    <td>{item.start_date} to {item.end_date}</td>
                    <td>{item.leave_type}</td>
                    <td>{item.days}</td>
                    <td><Badge type={item.status}>{item.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* MANAGER "Awaiting my decision" section */}
      {isManager && (
        <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="manager-decision-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="card-title" style={{ fontSize: '1rem', margin: 0 }}>
              Leaves Awaiting My Decision
            </h2>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              (among the first 100 pending leaves)
            </span>
          </div>

          {managerDecisionLeaves.loading ? (
            <Spinner />
          ) : managerDecisionLeaves.error ? (
            <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{managerDecisionLeaves.error}</div>
          ) : managerDecisionLeaves.items.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              No leave requests currently await your decision.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Employee ID</th>
                  <th>Dates</th>
                  <th>Days</th>
                  <th>Reason</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {managerDecisionLeaves.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.employee_id}</td>
                    <td>{item.start_date} to {item.end_date}</td>
                    <td>{item.days}</td>
                    <td>{item.reason || '—'}</td>
                    <td><Badge type={item.status}>{item.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Latest Notifications List (EMPLOYEE, MANAGER) */}
      {(isEmployee || isManager) && (
        <div className="card" data-testid="dashboard-notifications-card">
          <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '1rem' }}>
            Latest Notifications
          </h2>
          {notifications.loading ? (
            <Spinner />
          ) : notifications.error ? (
            <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }}>{notifications.error}</div>
          ) : notifications.items.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No recent notifications.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {notifications.items.map((notif) => (
                <div
                  key={notif.id}
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'var(--bg-primary)',
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem',
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <Badge type={notif.event_type}>{notif.event_type}</Badge>
                    <span style={{ marginLeft: '0.5rem', color: 'var(--text-primary)' }}>{notif.message}</span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {notif.created_at ? new Date(notif.created_at).toLocaleTimeString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
