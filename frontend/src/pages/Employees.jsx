import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api, ApiError } from '../lib/api.js';
import { can } from '../lib/permissions.js';
import { validateEmployeeForm } from '../lib/employeeRules.js';
import { DataTable } from '../components/DataTable.jsx';
import { Pagination } from '../components/Pagination.jsx';
import { Modal } from '../components/Modal.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { FormField } from '../components/FormField.jsx';
import { Toast } from '../components/Toast.jsx';
import { Badge } from '../components/Badge.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Employees({ user }) {
  const canWrite = can(user?.role, 'employee.write');

  // State
  const [employees, setEmployees] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Filter state
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [designationFilter, setDesignationFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [managerFilter, setManagerFilter] = useState('');
  const [pageFilter, setPageFilter] = useState('');

  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState({ type: 'error', message: '' });

  // Managers list for dropdown (max 100)
  const [managerOptions, setManagerOptions] = useState([]);

  // Modals state
  const [detailsModal, setDetailsModal] = useState({ isOpen: false, employee: null, loading: false });
  const [onboardModal, setOnboardModal] = useState({ isOpen: false });
  const [editModal, setEditModal] = useState({ isOpen: false, employee: null });
  const [deleteDialog, setDeleteDialog] = useState({ isOpen: false, employee: null });

  // Form states & loading
  const [onboardForm, setOnboardForm] = useState({
    name: '',
    email: '',
    department: '',
    designation: '',
    manager_id: '',
    role: 'EMPLOYEE',
    initial_password: '',
    monthly_salary: '',
  });
  const [onboardErrors, setOnboardErrors] = useState({});
  const [onboardingSubmitting, setOnboardingSubmitting] = useState(false);
  const [onboardSagaError, setOnboardSagaError] = useState('');

  const [editForm, setEditForm] = useState({
    id: '',
    name: '',
    email: '',
    department: '',
    designation: '',
    manager_id: '',
  });
  const [editErrors, setEditErrors] = useState({});
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  // Departments & Designations lists built dynamically from loaded data
  const [knownDepartments, setKnownDepartments] = useState([]);
  const [knownDesignations, setKnownDesignations] = useState([]);

  const showToast = (message, type = 'success') => {
    setToast({ type, message });
    setTimeout(() => setToast({ type: 'error', message: '' }), 5000);
  };

  // Fetch employees list
  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/employees?page=${page}&page_size=${pageSize}`;
      if (departmentFilter) {
        url += `&department=${encodeURIComponent(departmentFilter)}`;
      }
      const res = await api.get(url);
      if (res) {
        setEmployees(res.items || []);
        setTotal(res.total || 0);

        // Update known departments & designations
        if (res.items) {
          const depts = new Set(res.items.map((e) => e.department).filter(Boolean));
          setKnownDepartments((prev) => Array.from(new Set([...prev, ...depts])));

          const desigs = new Set(res.items.map((e) => e.designation).filter(Boolean));
          setKnownDesignations((prev) => Array.from(new Set([...prev, ...desigs])));
        }
      }
    } catch (err) {
      showToast(err.message || 'Failed to load employees', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, departmentFilter]);

  // Fetch manager choices (ACTIVE employees up to 100)
  const fetchManagerOptions = useCallback(async () => {
    try {
      const res = await api.get('/employees?page=1&page_size=100');
      if (res && res.items) {
        setManagerOptions(res.items.filter((e) => e.status === 'ACTIVE'));
      }
    } catch (err) {
      // Non-critical background load
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  useEffect(() => {
    if (canWrite) {
      fetchManagerOptions();
    }
  }, [canWrite, fetchManagerOptions]);

  // Filter current page client-side
  const filteredEmployees = useMemo(() => {
    return employees.filter((e) => {
      if (pageFilter.trim()) {
        const term = pageFilter.toLowerCase();
        const matchName = e.name && e.name.toLowerCase().includes(term);
        const matchEmail = e.email && e.email.toLowerCase().includes(term);
        if (!matchName && !matchEmail) return false;
      }
      if (designationFilter && e.designation !== designationFilter) return false;
      if (roleFilter && (e.role || '').toUpperCase() !== roleFilter.toUpperCase()) return false;
      if (managerFilter && e.manager_id !== managerFilter) return false;
      return true;
    });
  }, [employees, pageFilter, designationFilter, roleFilter, managerFilter]);

  // Manager ID to Name map
  const managerMap = useMemo(() => {
    const map = {};
    managerOptions.forEach((m) => {
      map[m.id] = m.name;
    });
    employees.forEach((e) => {
      map[e.id] = e.name;
    });
    return map;
  }, [managerOptions, employees]);

  // Row click handler
  const handleRowClick = async (emp) => {
    setDetailsModal({ isOpen: true, employee: null, loading: true });
    try {
      const details = await api.get(`/employees/${emp.id}`);
      setDetailsModal({ isOpen: true, employee: details || emp, loading: false });
    } catch (err) {
      setDetailsModal({ isOpen: true, employee: emp, loading: false });
    }
  };

  // Submit Onboard
  const handleOnboardSubmit = async (e) => {
    e.preventDefault();
    setOnboardSagaError('');
    const { isValid, errors } = validateEmployeeForm(onboardForm, true);
    setOnboardErrors(errors);
    if (!isValid) return;

    setOnboardingSubmitting(true);
    try {
      const payload = {
        name: onboardForm.name.trim(),
        email: onboardForm.email.trim(),
        department: onboardForm.department.trim(),
        designation: onboardForm.designation.trim(),
        manager_id: onboardForm.manager_id || null,
        role: onboardForm.role,
        initial_password: onboardForm.initial_password,
        monthly_salary: Number(onboardForm.monthly_salary),
      };

      await api.post('/employees', payload);

      showToast('Employee onboarding initiated successfully!', 'success');
      setOnboardModal({ isOpen: false });
      setOnboardForm({
        name: '',
        email: '',
        department: '',
        designation: '',
        manager_id: '',
        role: 'EMPLOYEE',
        initial_password: '',
        monthly_salary: '',
      });
      fetchEmployees();
      fetchManagerOptions();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 502 && err.code === 'ONBOARDING_FAILED') {
          setOnboardSagaError(
            'Onboarding steps were rolled back. A record with status ONBOARDING_FAILED now exists, and the email stays reserved.'
          );
        } else {
          showToast(err.message, 'error');
        }
      } else {
        showToast('An unexpected error occurred during onboarding.', 'error');
      }
    } finally {
      setOnboardingSubmitting(false);
    }
  };

  // Submit Edit
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const { isValid, errors } = validateEmployeeForm(editForm, false);
    setEditErrors(errors);
    if (!isValid) return;

    setEditSubmitting(true);
    try {
      const payload = {
        name: editForm.name.trim(),
        email: editForm.email.trim(),
        department: editForm.department.trim(),
        designation: editForm.designation.trim(),
        manager_id: editForm.manager_id || null,
      };

      await api.put(`/employees/${editForm.id}`, payload);
      showToast('Employee updated successfully!', 'success');
      setEditModal({ isOpen: false, employee: null });
      fetchEmployees();
      fetchManagerOptions();
    } catch (err) {
      showToast(err.message || 'Failed to update employee', 'error');
    } finally {
      setEditSubmitting(false);
    }
  };

  // Submit Delete
  const handleDeleteConfirm = async () => {
    if (!deleteDialog.employee) return;
    setDeleteSubmitting(true);
    try {
      await api.del(`/employees/${deleteDialog.employee.id}`);
      showToast('Employee deleted successfully', 'success');
      setDeleteDialog({ isOpen: false, employee: null });
      fetchEmployees();
      fetchManagerOptions();
    } catch (err) {
      showToast(err.message || 'Failed to delete employee', 'error');
    } finally {
      setDeleteSubmitting(false);
    }
  };

  // Columns definition
  const columns = [
    { header: 'Name', key: 'name' },
    { header: 'Email', key: 'email' },
    { header: 'Department', key: 'department' },
    { header: 'Designation', key: 'designation' },
    {
      header: 'Manager',
      render: (row) => (row.manager_id ? managerMap[row.manager_id] || row.manager_id.slice(0, 8) : '—'),
    },
    {
      header: 'Status',
      render: (row) => <Badge type={row.status}>{row.status}</Badge>,
    },
    {
      header: 'Actions',
      render: (row) => (
        <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', gap: '0.5rem' }}>
          {canWrite && (
            <>
              <button
                className="btn btn-secondary"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                onClick={() => {
                  setEditForm({
                    id: row.id,
                    name: row.name || '',
                    email: row.email || '',
                    department: row.department || '',
                    designation: row.designation || '',
                    manager_id: row.manager_id || '',
                  });
                  setEditErrors({});
                  setEditModal({ isOpen: true, employee: row });
                }}
                data-testid={`edit-btn-${row.id}`}
              >
                Edit
              </button>
              <button
                className="btn btn-danger"
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                onClick={() => setDeleteDialog({ isOpen: true, employee: row })}
                data-testid={`delete-btn-${row.id}`}
              >
                Delete
              </button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 className="card-title" style={{ margin: 0 }}>
            Employee Directory
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Manage employee records and onboarding.
          </p>
        </div>
        {canWrite && (
          <button
            className="btn btn-primary"
            onClick={() => {
              setOnboardSagaError('');
              setOnboardErrors({});
              setOnboardModal({ isOpen: true });
            }}
            data-testid="onboard-employee-btn"
          >
            + Onboard Employee
          </button>
        )}
      </div>

      <Toast type={toast.type} message={toast.message} />

      {/* Filters bar */}
      <div className="card" style={{ padding: '1rem', marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }} data-testid="employee-filter-bar">
        <div style={{ flex: 1, minWidth: '180px' }}>
          <label className="form-label" htmlFor="page-filter">
            Search (Name / Email)
          </label>
          <input
            id="page-filter"
            type="text"
            className="form-input"
            placeholder="Search name or email..."
            value={pageFilter}
            onChange={(e) => setPageFilter(e.target.value)}
            data-testid="employee-search-input"
          />
        </div>

        <div style={{ flex: 1, minWidth: '150px' }}>
          <label className="form-label" htmlFor="dept-select">
            Department
          </label>
          <select
            id="dept-select"
            className="form-select"
            value={departmentFilter}
            onChange={(e) => {
              setDepartmentFilter(e.target.value);
              setPage(1);
            }}
            data-testid="employee-dept-select"
          >
            <option value="">All Departments</option>
            {knownDepartments.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, minWidth: '150px' }}>
          <label className="form-label" htmlFor="desig-select">
            Designation
          </label>
          <select
            id="desig-select"
            className="form-select"
            value={designationFilter}
            onChange={(e) => setDesignationFilter(e.target.value)}
            data-testid="employee-desig-select"
          >
            <option value="">All Designations</option>
            {knownDesignations.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, minWidth: '130px' }}>
          <label className="form-label" htmlFor="role-select">
            Role
          </label>
          <select
            id="role-select"
            className="form-select"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            data-testid="employee-role-select"
          >
            <option value="">All Roles</option>
            <option value="EMPLOYEE">EMPLOYEE</option>
            <option value="MANAGER">MANAGER</option>
            <option value="HR">HR</option>
            <option value="ADMIN">ADMIN</option>
          </select>
        </div>

        <div style={{ flex: 1, minWidth: '160px' }}>
          <label className="form-label" htmlFor="manager-select">
            Reporting Manager
          </label>
          <select
            id="manager-select"
            className="form-select"
            value={managerFilter}
            onChange={(e) => setManagerFilter(e.target.value)}
            data-testid="employee-manager-select"
          >
            <option value="">All Managers</option>
            {managerOptions.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={filteredEmployees}
        loading={loading}
        onRowClick={handleRowClick}
        emptyMessage="No employees found matching filter criteria."
      />

      {/* Pagination */}
      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={(p) => setPage(p)}
        onPageSizeChange={(ps) => {
          setPageSize(ps);
          setPage(1);
        }}
      />

      {/* Details Modal */}
      <Modal
        isOpen={detailsModal.isOpen}
        onClose={() => setDetailsModal({ isOpen: false, employee: null, loading: false })}
        title="Employee Details"
      >
        {detailsModal.loading ? (
          <Spinner />
        ) : detailsModal.employee ? (
          <div>
            <p><strong>ID:</strong> {detailsModal.employee.id}</p>
            <p><strong>Name:</strong> {detailsModal.employee.name}</p>
            <p><strong>Email:</strong> {detailsModal.employee.email}</p>
            <p><strong>Department:</strong> {detailsModal.employee.department}</p>
            <p><strong>Designation:</strong> {detailsModal.employee.designation}</p>
            <p><strong>Manager:</strong> {detailsModal.employee.manager_id ? (managerMap[detailsModal.employee.manager_id] || detailsModal.employee.manager_id) : 'None'}</p>
            <p><strong>Status:</strong> <Badge type={detailsModal.employee.status}>{detailsModal.employee.status}</Badge></p>
            {detailsModal.employee.created_at && <p><strong>Created At:</strong> {detailsModal.employee.created_at}</p>}
          </div>
        ) : null}
      </Modal>

      {/* Onboard Modal */}
      <Modal
        isOpen={onboardModal.isOpen}
        onClose={() => !onboardingSubmitting && setOnboardModal({ isOpen: false })}
        title="Onboard New Employee"
      >
        {onboardSagaError && (
          <div className="toast toast-error" style={{ marginBottom: '1rem' }} data-testid="onboarding-saga-error">
            {onboardSagaError}
          </div>
        )}

        {onboardingSubmitting && (
          <div style={{ textAlign: 'center', margin: '1rem 0', color: 'var(--accent-primary)' }}>
            <Spinner />
            <p style={{ marginTop: '0.5rem', fontWeight: 500 }}>
              Onboarding in progress: creating account and payroll profile...
            </p>
          </div>
        )}

        <form onSubmit={handleOnboardSubmit}>
          <FormField label="Full Name" required error={onboardErrors.name} id="onboard-name">
            <input
              id="onboard-name"
              type="text"
              className="form-input"
              value={onboardForm.name}
              onChange={(e) => setOnboardForm({ ...onboardForm, name: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <FormField label="Email Address" required error={onboardErrors.email} id="onboard-email">
            <input
              id="onboard-email"
              type="email"
              className="form-input"
              value={onboardForm.email}
              onChange={(e) => setOnboardForm({ ...onboardForm, email: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <FormField label="Department" required error={onboardErrors.department} id="onboard-dept">
            <input
              id="onboard-dept"
              type="text"
              className="form-input"
              value={onboardForm.department}
              onChange={(e) => setOnboardForm({ ...onboardForm, department: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <FormField label="Designation" required error={onboardErrors.designation} id="onboard-desig">
            <input
              id="onboard-desig"
              type="text"
              className="form-input"
              value={onboardForm.designation}
              onChange={(e) => setOnboardForm({ ...onboardForm, designation: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <FormField label="Manager" error={onboardErrors.manager_id} id="onboard-manager">
            <select
              id="onboard-manager"
              className="form-select"
              value={onboardForm.manager_id}
              onChange={(e) => setOnboardForm({ ...onboardForm, manager_id: e.target.value })}
              disabled={onboardingSubmitting}
            >
              <option value="">-- No Manager --</option>
              {managerOptions.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.email})
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="System Role" required id="onboard-role">
            <select
              id="onboard-role"
              className="form-select"
              value={onboardForm.role}
              onChange={(e) => setOnboardForm({ ...onboardForm, role: e.target.value })}
              disabled={onboardingSubmitting}
            >
              <option value="EMPLOYEE">EMPLOYEE</option>
              <option value="MANAGER">MANAGER</option>
              <option value="HR">HR</option>
              <option value="ADMIN">ADMIN</option>
            </select>
          </FormField>

          <FormField label="Initial Password" required error={onboardErrors.initial_password} id="onboard-pass">
            <input
              id="onboard-pass"
              type="password"
              className="form-input"
              value={onboardForm.initial_password}
              onChange={(e) => setOnboardForm({ ...onboardForm, initial_password: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <FormField label="Monthly Salary" required error={onboardErrors.monthly_salary} id="onboard-salary">
            <input
              id="onboard-salary"
              type="number"
              step="0.01"
              className="form-input"
              value={onboardForm.monthly_salary}
              onChange={(e) => setOnboardForm({ ...onboardForm, monthly_salary: e.target.value })}
              disabled={onboardingSubmitting}
            />
          </FormField>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setOnboardModal({ isOpen: false })}
              disabled={onboardingSubmitting}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={onboardingSubmitting} data-testid="submit-onboard-btn">
              {onboardingSubmitting ? 'Onboarding...' : 'Submit Onboarding'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={editModal.isOpen}
        onClose={() => !editSubmitting && setEditModal({ isOpen: false, employee: null })}
        title="Edit Employee"
      >
        <form onSubmit={handleEditSubmit}>
          <FormField label="Full Name" required error={editErrors.name} id="edit-name">
            <input
              id="edit-name"
              type="text"
              className="form-input"
              value={editForm.name}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              disabled={editSubmitting}
            />
          </FormField>

          <FormField label="Email Address" required error={editErrors.email} id="edit-email">
            <input
              id="edit-email"
              type="email"
              className="form-input"
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              disabled={editSubmitting}
            />
          </FormField>

          <FormField label="Department" required error={editErrors.department} id="edit-dept">
            <input
              id="edit-dept"
              type="text"
              className="form-input"
              value={editForm.department}
              onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
              disabled={editSubmitting}
            />
          </FormField>

          <FormField label="Designation" required error={editErrors.designation} id="edit-desig">
            <input
              id="edit-desig"
              type="text"
              className="form-input"
              value={editForm.designation}
              onChange={(e) => setEditForm({ ...editForm, designation: e.target.value })}
              disabled={editSubmitting}
            />
          </FormField>

          <FormField label="Manager" error={editErrors.manager_id} id="edit-manager">
            <select
              id="edit-manager"
              className="form-select"
              value={editForm.manager_id}
              onChange={(e) => setEditForm({ ...editForm, manager_id: e.target.value })}
              disabled={editSubmitting}
            >
              <option value="">-- No Manager --</option>
              {managerOptions
                .filter((m) => m.id !== editForm.id)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.email})
                  </option>
                ))}
            </select>
          </FormField>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setEditModal({ isOpen: false, employee: null })}
              disabled={editSubmitting}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={editSubmitting} data-testid="submit-edit-btn">
              {editSubmitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Dialog */}
      <ConfirmDialog
        isOpen={deleteDialog.isOpen}
        onClose={() => setDeleteDialog({ isOpen: false, employee: null })}
        onConfirm={handleDeleteConfirm}
        title="Delete Employee"
        message={`Are you sure you want to delete employee "${deleteDialog.employee?.name}"?`}
        confirmLabel="Delete Employee"
        isDanger={true}
        loading={deleteSubmitting}
      />
    </div>
  );
}
