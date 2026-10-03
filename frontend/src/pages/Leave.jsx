import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, ApiError } from '../lib/api.js';
import { leaveActions, canCreateFor } from '../lib/leaveRules.js';
import { countWeekdays, validateLeaveRange } from '../lib/dates.js';
import { ROLES } from '../lib/permissions.js';
import { DataTable } from '../components/DataTable.jsx';
import { Pagination } from '../components/Pagination.jsx';
import { FormField } from '../components/FormField.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { Toast } from '../components/Toast.jsx';
import { Badge } from '../components/Badge.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Leave({ user }) {
  const currentYear = new Date().getUTCFullYear();

  // State
  const [employeeMap, setEmployeeMap] = useState({});
  const [employeeList, setEmployeeList] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('');
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'needs_decision'
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState({ type: 'error', message: '' });

  // Balance Card State
  const isManagementAdminHR = [ROLES.ADMIN, ROLES.HR].includes(user?.role);
  const [balanceSubjectId, setBalanceSubjectId] = useState(isManagementAdminHR ? '' : user?.id || '');
  const [balanceYear, setBalanceYear] = useState(currentYear);
  const [balance, setBalance] = useState(null);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [balanceError, setBalanceError] = useState(null);

  // Leave Form State
  const [formEmployeeId, setFormEmployeeId] = useState(isManagementAdminHR ? '' : user?.id || '');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [leaveType, setLeaveType] = useState('PAID');
  const [reason, setReason] = useState('');
  const [requestSubmitting, setRequestSubmitting] = useState(false);

  // Dialog State
  const [actionDialog, setActionDialog] = useState({
    isOpen: false,
    actionType: '', // 'reject' | 'cancel'
    leave: null,
  });
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const showToast = (message, type = 'success') => {
    setToast({ type, message });
    setTimeout(() => setToast({ type: 'error', message: '' }), 5000);
  };

  // 1. Fetch 100 Employees for Name Resolution Map & Subject Dropdowns
  const fetchEmployeesMap = useCallback(async () => {
    try {
      const res = await api.get('/employees?page=1&page_size=100');
      if (res && res.items) {
        setEmployeeList(res.items);
        const map = {};
        res.items.forEach((emp) => {
          map[emp.id] = emp.name;
        });
        setEmployeeMap(map);
      }
    } catch (err) {
      // Non-critical background failure
    }
  }, []);

  // 2. Fetch Leave Balance for selected subject & year
  const fetchBalance = useCallback(async () => {
    if (!balanceSubjectId) {
      setBalance(null);
      setBalanceError(null);
      return;
    }
    setBalanceLoading(true);
    setBalanceError(null);
    try {
      const res = await api.get(`/leaves/balance/${balanceSubjectId}?year=${balanceYear}`);
      setBalance(res || null);
    } catch (err) {
      setBalance(null);
      const errMsg = err.message || 'Failed to fetch leave balance';
      setBalanceError(errMsg);
      if (err instanceof ApiError && err.status === 404) {
        // Employee not found in payroll
      } else {
        showToast(errMsg, 'error');
      }
    } finally {
      setBalanceLoading(false);
    }
  }, [balanceSubjectId, balanceYear]);

  // 3. Fetch Leaves Table
  const fetchLeaves = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/leaves?page=${page}&page_size=${pageSize}`;
      if (statusFilter) {
        url += `&status=${statusFilter}`;
      }
      const res = await api.get(url);
      if (res) {
        setLeaves(res.items || []);
        setTotal(res.total || 0);
      }
    } catch (err) {
      showToast(err.message || 'Failed to fetch leaves', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    fetchEmployeesMap();
  }, [fetchEmployeesMap]);

  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  useEffect(() => {
    fetchLeaves();
  }, [fetchLeaves]);

  // Compute live range validation and weekday count
  const rangeValidationError = useMemo(() => {
    if (!startDate || !endDate) return null;
    return validateLeaveRange(startDate, endDate);
  }, [startDate, endDate]);

  const liveDaysCount = useMemo(() => {
    if (!startDate || !endDate) return 0;
    return countWeekdays(startDate, endDate);
  }, [startDate, endDate]);

  // Filter leaves for "Needs my decision" tab
  const displayedLeaves = useMemo(() => {
    if (activeTab === 'needs_decision') {
      return leaves.filter((row) => {
        const { canApprove } = leaveActions(user, row);
        return row.status === 'PENDING' && canApprove;
      });
    }
    return leaves;
  }, [leaves, activeTab, user]);

  // Submit Request Leave
  const handleRequestSubmit = async (e) => {
    e.preventDefault();
    const valError = validateLeaveRange(startDate, endDate);
    if (valError) {
      showToast(valError, 'error');
      return;
    }

    const targetEmpId = formEmployeeId || user?.id;
    if (!canCreateFor(user, targetEmpId)) {
      showToast('You are not allowed to request leave for this employee.', 'error');
      return;
    }

    setRequestSubmitting(true);
    try {
      const payload = {
        employee_id: targetEmpId,
        start_date: startDate,
        end_date: endDate,
        leave_type: leaveType,
        reason: reason.trim() || undefined,
      };

      await api.post('/leaves', payload);
      showToast('Leave request submitted successfully!', 'success');
      setStartDate('');
      setEndDate('');
      setReason('');
      fetchLeaves();
      fetchBalance();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503 && err.code === 'EMPLOYEE_SERVICE_UNAVAILABLE') {
          showToast('Employee service temporarily unavailable, try again', 'error');
        } else {
          showToast(err.message, 'error');
        }
      } else {
        showToast('Failed to submit leave request.', 'error');
      }
    } finally {
      setRequestSubmitting(false);
    }
  };

  // Action Handlers (Approve / Reject / Cancel)
  const handleApprove = async (leave) => {
    try {
      await api.post(`/leaves/${leave.id}/approve`, {});
      showToast('Leave request approved', 'success');
      fetchLeaves();
      fetchBalance();
    } catch (err) {
      showToast(err.message || 'Failed to approve leave', 'error');
      fetchLeaves();
    }
  };

  const handleActionConfirm = async () => {
    const { actionType, leave } = actionDialog;
    if (!leave) return;

    setActionSubmitting(true);
    try {
      if (actionType === 'reject') {
        await api.post(`/leaves/${leave.id}/reject`, {});
        showToast('Leave request rejected', 'success');
      } else if (actionType === 'cancel') {
        await api.post(`/leaves/${leave.id}/cancel`, {});
        showToast('Leave request cancelled', 'success');
      }
      setActionDialog({ isOpen: false, actionType: '', leave: null });
      fetchLeaves();
      fetchBalance();
    } catch (err) {
      showToast(err.message || `Failed to ${actionType} leave`, 'error');
      fetchLeaves();
    } finally {
      setActionSubmitting(false);
    }
  };

  // Helper name resolver
  const resolveName = (empId) => {
    if (!empId) return '—';
    return employeeMap[empId] || empId.slice(0, 8);
  };

  // Table Columns
  const columns = [
    {
      header: 'Employee',
      render: (row) => resolveName(row.employee_id),
    },
    {
      header: 'Dates',
      render: (row) => `${row.start_date} to ${row.end_date}`,
    },
    { header: 'Type', key: 'leave_type' },
    { header: 'Days', key: 'days' },
    { header: 'Reason', render: (row) => row.reason || '—' },
    {
      header: 'Status',
      render: (row) => <Badge type={row.status}>{row.status}</Badge>,
    },
    {
      header: 'Decided By',
      render: (row) => (row.decided_by ? resolveName(row.decided_by) : '—'),
    },
    {
      header: 'Actions',
      render: (row) => {
        const { canApprove, canReject, canCancel } = leaveActions(user, row);
        return (
          <div style={{ display: 'flex', gap: '0.375rem' }}>
            {canApprove && (
              <button
                className="btn btn-primary"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                onClick={() => handleApprove(row)}
                data-testid={`approve-btn-${row.id}`}
              >
                Approve
              </button>
            )}
            {canReject && (
              <button
                className="btn btn-danger"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                onClick={() => setActionDialog({ isOpen: true, actionType: 'reject', leave: row })}
                data-testid={`reject-btn-${row.id}`}
              >
                Reject
              </button>
            )}
            {canCancel && (
              <button
                className="btn btn-secondary"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                onClick={() => setActionDialog({ isOpen: true, actionType: 'cancel', leave: row })}
                data-testid={`cancel-btn-${row.id}`}
              >
                Cancel
              </button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="card-title" style={{ margin: 0 }}>
          Leave Management
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Track leave balance, submit requests, and handle approvals.
        </p>
      </div>

      <Toast type={toast.type} message={toast.message} />

      {/* Balance Summary Card */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className="card-title" style={{ margin: 0, fontSize: '1rem' }}>
            Leave Balance Summary
          </h2>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            {isManagementAdminHR && (
              <select
                className="form-select"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.875rem' }}
                value={balanceSubjectId}
                onChange={(e) => setBalanceSubjectId(e.target.value)}
                data-testid="balance-employee-select"
              >
                <option value="">-- Select Employee --</option>
                {employeeList.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} ({emp.email})
                  </option>
                ))}
              </select>
            )}
            <select
              className="form-select"
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.875rem', width: 'auto' }}
              value={balanceYear}
              onChange={(e) => setBalanceYear(Number(e.target.value))}
            >
              <option value={currentYear - 1}>{currentYear - 1}</option>
              <option value={currentYear}>{currentYear}</option>
              <option value={currentYear + 1}>{currentYear + 1}</option>
            </select>
          </div>
        </div>

        {balanceLoading ? (
          <Spinner />
        ) : balanceError ? (
          <div style={{ color: 'var(--accent-danger)', fontSize: '0.875rem' }} data-testid="balance-error-msg">
            {balanceError}
          </div>
        ) : !balanceSubjectId ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            Please select an employee to view leave balance.
          </div>
        ) : balance ? (
          <div>
            <div style={{ display: 'flex', gap: '2rem', marginBottom: '0.75rem', fontSize: '0.875rem' }}>
              <div>Allowance: <strong>{balance.allowance} days</strong></div>
              <div>Used: <strong>{balance.used} days</strong></div>
              <div>Remaining: <strong style={{ color: 'var(--accent-success)' }}>{balance.remaining} days</strong></div>
            </div>
            {/* Progress bar */}
            <div
              style={{
                width: '100%',
                height: '8px',
                backgroundColor: 'var(--bg-primary)',
                borderRadius: '4px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (balance.used / Math.max(1, balance.allowance)) * 100)}%`,
                  height: '100%',
                  backgroundColor: 'var(--accent-primary)',
                }}
              ></div>
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            No leave balance record available for this selection.
          </div>
        )}
      </div>

      {/* Request Leave Form */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '1rem' }}>
          Request Leave
        </h2>
        <form onSubmit={handleRequestSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            {isManagementAdminHR && (
              <FormField label="Employee" required id="req-emp-select">
                <select
                  id="req-emp-select"
                  className="form-select"
                  value={formEmployeeId}
                  onChange={(e) => setFormEmployeeId(e.target.value)}
                  disabled={requestSubmitting}
                >
                  <option value="">-- Select Subject --</option>
                  {employeeList.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name} ({emp.email})
                    </option>
                  ))}
                </select>
              </FormField>
            )}

            <FormField label="Start Date" required id="req-start">
              <input
                id="req-start"
                type="date"
                className="form-input"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={requestSubmitting}
              />
            </FormField>

            <FormField label="End Date" required id="req-end">
              <input
                id="req-end"
                type="date"
                className="form-input"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={requestSubmitting}
              />
            </FormField>

            <FormField label="Leave Type" required id="req-type">
              <select
                id="req-type"
                className="form-select"
                value={leaveType}
                onChange={(e) => setLeaveType(e.target.value)}
                disabled={requestSubmitting}
              >
                <option value="PAID">PAID</option>
                <option value="UNPAID">UNPAID</option>
              </select>
            </FormField>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <FormField label="Reason (Optional)" id="req-reason">
              <input
                id="req-reason"
                type="text"
                className="form-input"
                placeholder="Reason for leave..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={requestSubmitting}
              />
            </FormField>
          </div>

          {/* Validation & Weekday counter readout */}
          <div style={{ marginTop: '0.5rem', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {rangeValidationError ? (
              <div style={{ color: 'var(--accent-danger)' }}>{rangeValidationError}</div>
            ) : startDate && endDate ? (
              <div style={{ color: 'var(--accent-primary)' }}>
                Duration: <strong>{liveDaysCount}</strong> weekday(s)
              </div>
            ) : null}
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={requestSubmitting || !!rangeValidationError || liveDaysCount === 0}
            data-testid="submit-leave-request-btn"
          >
            {requestSubmitting ? 'Submitting...' : 'Submit Request'}
          </button>
        </form>
      </div>

      {/* Leave Requests Table Header with Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className={`btn ${activeTab === 'all' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('all')}
          >
            All Visible
          </button>
          {[ROLES.MANAGER, ROLES.HR, ROLES.ADMIN].includes(user?.role) && (
            <button
              className={`btn ${activeTab === 'needs_decision' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('needs_decision')}
              data-testid="tab-needs-decision"
            >
              Needs My Decision
            </button>
          )}
        </div>

        <div>
          <select
            className="form-select"
            style={{ width: 'auto', padding: '0.375rem 0.75rem' }}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">-- All Statuses --</option>
            <option value="PENDING">PENDING</option>
            <option value="APPROVED">APPROVED</option>
            <option value="REJECTED">REJECTED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={displayedLeaves}
        loading={loading}
        emptyMessage="No leave records found."
      />

      {/* Pagination */}
      <Pagination
        page={page}
        pageSize={pageSize}
        total={activeTab === 'needs_decision' ? displayedLeaves.length : total}
        onPageChange={(p) => setPage(p)}
        onPageSizeChange={(ps) => {
          setPageSize(ps);
          setPage(1);
        }}
      />

      {/* Confirm Dialog for Reject / Cancel */}
      <ConfirmDialog
        isOpen={actionDialog.isOpen}
        onClose={() => setActionDialog({ isOpen: false, actionType: '', leave: null })}
        onConfirm={handleActionConfirm}
        title={`${actionDialog.actionType === 'reject' ? 'Reject' : 'Cancel'} Leave Request`}
        message={`Are you sure you want to ${actionDialog.actionType} this leave request for ${
          actionDialog.leave ? resolveName(actionDialog.leave.employee_id) : 'this employee'
        }?`}
        confirmLabel={`${actionDialog.actionType === 'reject' ? 'Reject' : 'Cancel'} Leave`}
        isDanger={true}
        loading={actionSubmitting}
      />
    </div>
  );
}
