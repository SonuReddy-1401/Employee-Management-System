import React, { useState, useEffect, useCallback } from 'react';
import { api, ApiError } from '../lib/api.js';
import { ROLES } from '../lib/permissions.js';
import { Badge } from '../components/Badge.jsx';
import { EmptyState } from '../components/EmptyState.jsx';
import { Toast } from '../components/Toast.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Notifications({ user }) {
  const isHRorAdmin = [ROLES.ADMIN, ROLES.HR].includes(user?.role);

  const [employeeList, setEmployeeList] = useState([]);
  const [subjectId, setSubjectId] = useState(isHRorAdmin ? '' : user?.id || '');
  const [limit, setLimit] = useState(50);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState({ type: 'error', message: '' });

  const showToast = (message, type = 'success') => {
    setToast({ type, message });
    setTimeout(() => setToast({ type: 'error', message: '' }), 5000);
  };

  // Fetch employees list for subject selector (HR & ADMIN)
  useEffect(() => {
    if (isHRorAdmin) {
      api.get('/employees?page=1&page_size=100')
        .then((res) => {
          if (res && res.items) setEmployeeList(res.items);
        })
        .catch(() => {});
    }
  }, [isHRorAdmin]);

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    if (!subjectId) {
      setNotifications([]);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get(`/notifications/${subjectId}?limit=${limit}`);
      setNotifications(res || []);
    } catch (err) {
      setNotifications([]);
      if (err instanceof ApiError && (err.status === 403 || err.status === 401)) {
        showToast('You are not authorized to view notifications for this user.', 'error');
      } else {
        showToast(err.message || 'Failed to fetch notifications.', 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [subjectId, limit]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const getEventBadgeType = (type) => {
    switch (type) {
      case 'EmployeeOnboarded':
      case 'LeaveApproved':
        return 'approved';
      case 'LeaveRequested':
        return 'pending';
      case 'LeaveRejected':
        return 'rejected';
      case 'LeaveCancelled':
        return 'cancelled';
      default:
        return 'active';
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 className="card-title" style={{ margin: 0 }}>
            Notifications & Audit Log
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            System event log and user activity notifications.
          </p>
        </div>

        <button
          className="btn btn-secondary"
          onClick={fetchNotifications}
          disabled={loading}
          data-testid="refresh-notifications-btn"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <Toast type={toast.type} message={toast.message} />

      {/* Controls Bar */}
      <div className="card" style={{ padding: '1rem', marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {isHRorAdmin && (
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label className="form-label" htmlFor="notif-emp-select">
              Select Employee Subject
            </label>
            <select
              id="notif-emp-select"
              className="form-select"
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              data-testid="notif-employee-select"
            >
              <option value="">-- Select Employee --</option>
              {employeeList.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name} ({emp.email})
                </option>
              ))}
            </select>
          </div>
        )}

        <div style={{ width: '150px' }}>
          <label className="form-label" htmlFor="notif-limit-select">
            Limit
          </label>
          <select
            id="notif-limit-select"
            className="form-select"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            data-testid="notif-limit-select"
          >
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
        </div>
      </div>

      {/* Notifications List */}
      <div className="card">
        {loading ? (
          <Spinner />
        ) : !subjectId ? (
          <EmptyState message="Please select an employee to view notifications." />
        ) : notifications.length === 0 ? (
          <EmptyState message="No notifications found for this user." />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }} data-testid="notifications-list">
            {notifications.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: '1rem',
                  border: '1px solid var(--border-color)',
                  borderRadius: '0.375rem',
                  backgroundColor: 'var(--bg-primary)',
                  display: 'flex',
                  justify: 'space-between',
                  alignItems: 'flex-start',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ marginBottom: '0.375rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <Badge type={getEventBadgeType(item.event_type)}>{item.event_type}</Badge>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-primary)', fontSize: '0.875rem' }}>{item.message}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
