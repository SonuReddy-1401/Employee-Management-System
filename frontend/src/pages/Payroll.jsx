import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, ApiError } from '../lib/api.js';
import { formatMoney } from '../lib/money.js';
import { countWeekdays } from '../lib/dates.js';
import { ROLES } from '../lib/permissions.js';
import { DataTable } from '../components/DataTable.jsx';
import { Modal } from '../components/Modal.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { FormField } from '../components/FormField.jsx';
import { Toast } from '../components/Toast.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Payroll({ user }) {
  const isHRorAdmin = [ROLES.ADMIN, ROLES.HR].includes(user?.role);
  const now = new Date();
  const currentMonthStr = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;

  // Employee selector list for HR/ADMIN
  const [employeeList, setEmployeeList] = useState([]);
  const [subjectId, setSubjectId] = useState(isHRorAdmin ? '' : user?.id || '');

  // Payslips list
  const [payslips, setPayslips] = useState([]);
  const [loadingPayslips, setLoadingPayslips] = useState(false);
  const [toast, setToast] = useState({ type: 'error', message: '' });

  // Run Payroll state
  const [runMonth, setRunMonth] = useState(currentMonthStr);
  const [runMonthError, setRunMonthError] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [runningPayroll, setRunningPayroll] = useState(false);
  const [runResult, setRunResult] = useState(null);

  // Breakdown Modal state
  const [detailModal, setDetailModal] = useState({ isOpen: false, payslip: null });

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

  // Fetch payslips for selected subject
  const fetchPayslips = useCallback(async () => {
    if (!subjectId) {
      setPayslips([]);
      return;
    }
    setLoadingPayslips(true);
    try {
      const res = await api.get(`/payslips/${subjectId}`);
      setPayslips(res || []);
    } catch (err) {
      setPayslips([]);
      if (err instanceof ApiError && err.status === 404) {
        // No payslips found
      } else {
        showToast(err.message || 'Failed to fetch payslips', 'error');
      }
    } finally {
      setLoadingPayslips(false);
    }
  }, [subjectId]);

  useEffect(() => {
    fetchPayslips();
  }, [fetchPayslips]);

  // Validate run month
  const isFutureMonth = useMemo(() => {
    if (!/^\d{4}-\d{2}$/.test(runMonth)) return false;
    return runMonth > currentMonthStr;
  }, [runMonth, currentMonthStr]);

  const handleRunClick = (e) => {
    e.preventDefault();
    setRunMonthError('');
    if (!/^\d{4}-\d{2}$/.test(runMonth)) {
      setRunMonthError('Month must be in YYYY-MM format.');
      return;
    }
    setConfirmOpen(true);
  };

  const handleRunConfirm = async () => {
    setRunningPayroll(true);
    setRunResult(null);
    try {
      const res = await api.post(`/payroll/run?month=${runMonth}`, {});
      setRunResult(res);
      showToast(`Payroll run complete. Created: ${res.created}, Skipped: ${res.skipped}`, 'success');
      setConfirmOpen(false);
      fetchPayslips();
    } catch (err) {
      if (err instanceof ApiError) {
        showToast(err.message, 'error');
      } else {
        showToast('Failed to run payroll.', 'error');
      }
    } finally {
      setRunningPayroll(false);
    }
  };

  // Calculate working days in month using dates.js
  const getWorkingDaysInMonth = (monthStr) => {
    if (!monthStr || !/^\d{4}-\d{2}$/.test(monthStr)) return 0;
    const [year, month] = monthStr.split('-').map(Number);
    const firstDay = `${monthStr}-01`;
    const lastDayNum = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const lastDay = `${monthStr}-${String(lastDayNum).padStart(2, '0')}`;
    return countWeekdays(firstDay, lastDay);
  };

  const columns = [
    { header: 'Month', key: 'month' },
    { header: 'Gross Salary', render: (row) => `$${formatMoney(row.gross_salary)}` },
    { header: 'Unpaid Leave Days', key: 'unpaid_leave_days' },
    { header: 'Deductions', render: (row) => `$${formatMoney(row.deductions)}` },
    { header: 'Net Salary', render: (row) => `$${formatMoney(row.net_salary)}` },
    { header: 'Generated At', render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString() : '—' },
  ];

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="card-title" style={{ margin: 0 }}>
          Payroll & Payslips
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          View monthly payslips and run batch payroll.
        </p>
      </div>

      <Toast type={toast.type} message={toast.message} />

      {/* Run Payroll Card (HR and ADMIN only) */}
      {isHRorAdmin && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '1rem' }}>
            Run Monthly Payroll Batch
          </h2>
          <form onSubmit={handleRunClick} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <FormField label="Target Month (YYYY-MM)" required error={runMonthError} id="run-month">
                <input
                  id="run-month"
                  type="month"
                  className="form-input"
                  value={runMonth}
                  onChange={(e) => setRunMonth(e.target.value)}
                  disabled={runningPayroll}
                />
              </FormField>
            </div>

            <div style={{ marginBottom: runMonthError ? '1.5rem' : '0' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={runningPayroll}
                data-testid="run-payroll-btn"
              >
                {runningPayroll ? 'Processing...' : 'Run Payroll'}
              </button>
            </div>
          </form>

          {isFutureMonth && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--accent-warning)' }}>
              ⚠️ Note: Selected month is in the future.
            </div>
          )}

          {runResult && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', borderRadius: '0.375rem' }} data-testid="payroll-run-result">
              <strong>Payroll Run Summary:</strong> Created <strong>{runResult.created}</strong> payslips, Skipped <strong>{runResult.skipped}</strong> existing profiles.
            </div>
          )}
        </div>
      )}

      {/* Payslip Viewer Section */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className="card-title" style={{ fontSize: '1rem', margin: 0 }}>
            Payslip History
          </h2>

          {isHRorAdmin && (
            <select
              className="form-select"
              style={{ width: 'auto', padding: '0.25rem 0.5rem', fontSize: '0.875rem' }}
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              data-testid="payroll-employee-select"
            >
              <option value="">-- Select Employee --</option>
              {employeeList.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name} ({emp.email})
                </option>
              ))}
            </select>
          )}
        </div>

        {!subjectId ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '2rem 0', textAlign: 'center' }}>
            Please select an employee to view payslips.
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={payslips}
            loading={loadingPayslips}
            onRowClick={(row) => setDetailModal({ isOpen: true, payslip: row })}
            emptyMessage="No payslips found for this employee."
          />
        )}
      </div>

      {/* Run Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleRunConfirm}
        title="Confirm Payroll Run"
        message={`This will generate payslips for all active payroll profiles for month ${runMonth} and skip existing ones. Are you sure?`}
        confirmLabel="Run Payroll"
        isDanger={false}
        loading={runningPayroll}
      />

      {/* Breakdown Modal */}
      <Modal
        isOpen={detailModal.isOpen}
        onClose={() => setDetailModal({ isOpen: false, payslip: null })}
        title={`Payslip Breakdown - ${detailModal.payslip?.month || ''}`}
      >
        {detailModal.payslip && (
          <div>
            <p><strong>Gross Salary:</strong> ${formatMoney(detailModal.payslip.gross_salary)}</p>
            <p><strong>Unpaid Leave Days:</strong> {detailModal.payslip.unpaid_leave_days}</p>
            <p><strong>Deductions:</strong> ${formatMoney(detailModal.payslip.deductions)}</p>
            <p><strong>Net Salary:</strong> ${formatMoney(detailModal.payslip.net_salary)}</p>
            
            <div style={{ marginTop: '1.25rem', padding: '0.75rem', backgroundColor: 'var(--bg-primary)', borderRadius: '0.375rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              <div><strong>Calculation Rule:</strong></div>
              <div>deduction = gross salary / working days in the month x unpaid leave days</div>
              <div style={{ marginTop: '0.25rem' }}>
                Working days in {detailModal.payslip.month}: <strong>{getWorkingDaysInMonth(detailModal.payslip.month)}</strong> (computed from the contract rule)
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
