import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api.js';
import { ROLES } from '../lib/permissions.js';
import {
  getAttendanceRecords,
  getAttendanceForDate,
  getTodayStatus,
  clockIn,
  clockOut,
  getMonthDays,
  ATTENDANCE_STATUS,
  formatTime,
  getTodayDateString,
} from '../lib/attendance.js';
import { DataTable } from '../components/DataTable.jsx';
import { Badge } from '../components/Badge.jsx';
import { Spinner } from '../components/Spinner.jsx';
import { Toast } from '../components/Toast.jsx';

export function Attendance({ user }) {
  const isAdmin = user?.role === ROLES.ADMIN;
  const isManager = user?.role === ROLES.MANAGER;
  const isHR = user?.role === ROLES.HR;

  const initialTab = isAdmin ? 'emp_attendance' : 'my_attendance';
  const [activeTab, setActiveTab] = useState(initialTab);

  // Clock state
  const [todayRecord, setTodayRecord] = useState(null);
  const [toast, setToast] = useState({ type: 'error', message: '' });

  // Calendar state
  const currentDate = new Date();
  const [calendarYear] = useState(currentDate.getFullYear());
  const [calendarMonth] = useState(currentDate.getMonth());
  const [calendarDays, setCalendarDays] = useState([]);

  // Date picker & Filter state for Hierarchy table
  const [selectedDate, setSelectedDate] = useState(getTodayDateString());
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [designationFilter, setDesignationFilter] = useState('');
  const [managerFilter, setManagerFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Employees data for hierarchy view
  const [employeeList, setEmployeeList] = useState([]);
  const [loading, setLoading] = useState(false);

  const showToast = (message, type = 'success') => {
    setToast({ type, message });
    setTimeout(() => setToast({ type: 'error', message: '' }), 4000);
  };

  // Load today's clock status & month calendar
  const loadMyAttendance = useCallback(() => {
    if (!user?.id || isAdmin) return;
    const rec = getTodayStatus(user.id);
    setTodayRecord(rec);
    const days = getMonthDays(user.id, calendarYear, calendarMonth);
    setCalendarDays(days);
  }, [user?.id, isAdmin, calendarYear, calendarMonth]);

  // Load employees for hierarchy tabs
  const fetchEmployees = useCallback(async () => {
    if (![ROLES.ADMIN, ROLES.HR, ROLES.MANAGER].includes(user?.role)) return;
    setLoading(true);
    try {
      const res = await api.get('/employees?page=1&page_size=100');
      if (res && res.items) {
        setEmployeeList(res.items);
      }
    } catch (err) {
      showToast(err.message || 'Failed to fetch employee list', 'error');
    } finally {
      setLoading(false);
    }
  }, [user?.role]);

  useEffect(() => {
    loadMyAttendance();
  }, [loadMyAttendance]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  // Handle Clock In
  const handleClockIn = () => {
    const rec = clockIn(user.id);
    setTodayRecord(rec);
    showToast(`Clocked in successfully at ${rec.clockIn}!`, 'success');
    loadMyAttendance();
  };

  // Handle Clock Out / Logoff
  const handleClockOut = (customHour = null) => {
    const nowObj = new Date();
    const targetHour = customHour !== null ? customHour : nowObj.getHours();
    const timeStr = customHour !== null ? '04:15 PM' : formatTime(nowObj);

    const rec = clockOut(user.id, timeStr, targetHour);
    setTodayRecord(rec);

    if (rec.status === ATTENDANCE_STATUS.EARLY_LOGOFF) {
      showToast(`Logged off early at ${rec.clockOut} (Before 5:00 PM). Status: EARLY LOGOFF`, 'error');
    } else {
      showToast(`Logged off successfully at ${rec.clockOut}! Status: PRESENT`, 'success');
    }
    loadMyAttendance();
  };

  // Role categorization helpers (case-insensitive with designation fallback)
  const isManagerRole = (emp) => {
    if (!emp) return false;
    const r = (emp.role || '').toUpperCase();
    const d = (emp.designation || '').toLowerCase();
    return r === 'MANAGER' || d.includes('manager') || d.includes('lead');
  };

  const isHRRole = (emp) => {
    if (!emp) return false;
    const r = (emp.role || '').toUpperCase();
    const d = (emp.designation || '').toLowerCase();
    return r === 'HR' || d.includes('hr');
  };

  const isEmployeeRole = (emp) => {
    if (!emp) return false;
    return !isManagerRole(emp) && !isHRRole(emp) && (emp.role || '').toUpperCase() !== 'ADMIN';
  };

  // Dynamic filter dropdown options
  const departments = Array.from(new Set(employeeList.map((e) => e.department).filter(Boolean)));
  const designations = Array.from(new Set(employeeList.map((e) => e.designation).filter(Boolean)));
  const managers = employeeList.filter(
    (e) => isManagerRole(e) || (e.role || '').toUpperCase() === 'ADMIN'
  );

  // Filter staff list for Hierarchy tabs & dropdown filters
  const getHierarchyFilteredData = () => {
    let baseList = [];
    if (activeTab === 'team_attendance') {
      baseList = employeeList.filter((emp) => emp.manager_id === user?.id);
    } else if (activeTab === 'all_attendance') {
      baseList = employeeList;
    } else if (activeTab === 'emp_attendance') {
      baseList = employeeList.filter((emp) => isEmployeeRole(emp));
    } else if (activeTab === 'mgr_attendance') {
      baseList = employeeList.filter((emp) => isManagerRole(emp));
    } else if (activeTab === 'hr_attendance') {
      baseList = employeeList.filter((emp) => isHRRole(emp));
    }

    return baseList.filter((emp) => {
      if (departmentFilter && emp.department !== departmentFilter) return false;
      if (designationFilter && emp.designation !== designationFilter) return false;
      if (managerFilter && emp.manager_id !== managerFilter) return false;

      const userRec = getAttendanceForDate(emp.id, selectedDate);
      const effectiveStatus = userRec ? userRec.status : ATTENDANCE_STATUS.NOT_MARKED;

      if (statusFilter && effectiveStatus !== statusFilter) return false;

      return true;
    });
  };

  // Render status pill for table/calendar
  const renderStatusBadge = (status, clockOutTime) => {
    if (status === ATTENDANCE_STATUS.PRESENT) {
      return <Badge type="APPROVED">PRESENT</Badge>;
    }
    if (status === ATTENDANCE_STATUS.EARLY_LOGOFF) {
      return (
        <span
          className="badge badge-pending"
          style={{ backgroundColor: 'rgba(234, 179, 8, 0.18)', color: '#fde047', borderColor: 'rgba(234, 179, 8, 0.4)' }}
          title={`Early logoff at ${clockOutTime || '—'}`}
        >
          EARLY LOGOFF ({clockOutTime || 'Early'})
        </span>
      );
    }
    if (status === ATTENDANCE_STATUS.ABSENT) {
      return <Badge type="REJECTED">ABSENT</Badge>;
    }
    if (status === ATTENDANCE_STATUS.NOT_MARKED) {
      return (
        <span
          className="badge badge-cancelled"
          style={{ backgroundColor: 'rgba(113, 113, 122, 0.18)', color: '#a1a1aa', borderColor: 'rgba(113, 113, 122, 0.3)' }}
          title="Attendance not punched yet for this date"
        >
          NOT MARKED YET
        </span>
      );
    }
    return <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{status}</span>;
  };

  // Columns for Hierarchy Data Table
  const hierarchyColumns = [
    { header: 'Employee Name', key: 'name' },
    { header: 'Email', key: 'email' },
    { header: 'Department', render: (row) => row.department || '—' },
    { header: 'Designation', render: (row) => row.designation || '—' },
    {
      header: 'Reporting Manager',
      render: (row) => {
        const mgr = employeeList.find((e) => e.id === row.manager_id);
        return mgr ? mgr.name : '—';
      },
    },
    {
      header: 'Attendance Status',
      render: (row) => {
        const userRec = getAttendanceForDate(row.id, selectedDate);
        const st = userRec ? userRec.status : ATTENDANCE_STATUS.NOT_MARKED;
        return renderStatusBadge(st, userRec?.clockOut);
      },
    },
    {
      header: 'Clock In Time',
      render: (row) => {
        const userRec = getAttendanceForDate(row.id, selectedDate);
        return userRec?.clockIn || '—';
      },
    },
    {
      header: 'Logoff Time',
      render: (row) => {
        const userRec = getAttendanceForDate(row.id, selectedDate);
        return userRec?.clockOut || '—';
      },
    },
  ];

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="card-title" style={{ margin: 0 }}>
          Attendance & Work Log
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Mark daily attendance, record logoff timestamps, and view attendance across organizational hierarchy.
        </p>
      </div>

      <Toast type={toast.type} message={toast.message} />

      {/* Navigation Tabs Header */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
        {!isAdmin && (
          <button
            className={`btn ${activeTab === 'my_attendance' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('my_attendance')}
            data-testid="tab-my-attendance"
          >
            My Attendance & Calendar
          </button>
        )}

        {isManager && (
          <button
            className={`btn ${activeTab === 'team_attendance' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('team_attendance')}
            data-testid="tab-team-attendance"
          >
            Team Attendance (Direct Reports)
          </button>
        )}

        {isHR && (
          <button
            className={`btn ${activeTab === 'all_attendance' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('all_attendance')}
            data-testid="tab-all-attendance"
          >
            Employee Attendance (All Staff)
          </button>
        )}

        {isAdmin && (
          <>
            <button
              className={`btn ${activeTab === 'emp_attendance' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('emp_attendance')}
              data-testid="tab-admin-employees"
            >
              Employees
            </button>
            <button
              className={`btn ${activeTab === 'mgr_attendance' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('mgr_attendance')}
              data-testid="tab-admin-managers"
            >
              Managers
            </button>
            <button
              className={`btn ${activeTab === 'hr_attendance' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActiveTab('hr_attendance')}
              data-testid="tab-admin-hr"
            >
              HR Staff
            </button>
          </>
        )}
      </div>

      {/* Tab 1: My Attendance & Calendar (Enabled for EMPLOYEE, MANAGER, HR) */}
      {activeTab === 'my_attendance' && !isAdmin && (
        <>
          {/* Clock In / Logoff Action Card */}
          <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="clock-action-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h2 className="card-title" style={{ margin: 0, fontSize: '1rem' }}>
                  Daily Attendance Punch ({getTodayDateString()})
                </h2>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  Standard Working Hours: <strong>09:00 AM – 05:00 PM</strong>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ textAlign: 'right', fontSize: '0.85rem' }}>
                  <div>Clock In: <strong>{todayRecord?.clockIn || 'Not Clocked In'}</strong></div>
                  <div>Logoff: <strong>{todayRecord?.clockOut || 'Not Logged Off'}</strong></div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    className="btn btn-primary"
                    onClick={handleClockIn}
                    disabled={!!todayRecord?.clockIn}
                    data-testid="clock-in-btn"
                  >
                    {todayRecord?.clockIn ? 'Clocked In' : 'Clock In'}
                  </button>

                  <button
                    className="btn btn-secondary"
                    onClick={() => handleClockOut()}
                    disabled={!todayRecord?.clockIn || !!todayRecord?.clockOut}
                    data-testid="clock-out-btn"
                  >
                    {todayRecord?.clockOut ? 'Logged Off' : 'Logoff (Clock Out)'}
                  </button>

                  {/* Early Logoff test action button */}
                  {todayRecord?.clockIn && !todayRecord?.clockOut && (
                    <button
                      className="btn btn-danger"
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                      onClick={() => handleClockOut(16)} // 4:00 PM (16:00 < 17:00 -> Early Logoff)
                      data-testid="early-logoff-btn"
                    >
                      Logoff Early (4:00 PM)
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Today's status bar */}
            <div style={{ marginTop: '1rem', paddingTop: '0.875rem', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Today's Status:</span>
              {todayRecord ? (
                renderStatusBadge(todayRecord.status, todayRecord.clockOut)
              ) : (
                <span className="badge badge-cancelled">NOT PUNCHED YET</span>
              )}
            </div>
          </div>

          {/* Calendar View Card */}
          <div className="card" data-testid="attendance-calendar-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h2 className="card-title" style={{ margin: 0, fontSize: '1rem' }}>
                Attendance Calendar — {monthNames[calendarMonth]} {calendarYear}
              </h2>

              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.775rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: 'var(--accent-success)' }}></span> Present (Green)
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: 'var(--accent-warning)' }}></span> Early Logoff (Yellow)
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: 'var(--accent-danger)' }}></span> Absent (Red)
                </span>
              </div>
            </div>

            {/* Calendar Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.5rem' }} data-testid="calendar-grid">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                <div
                  key={d}
                  style={{
                    textAlign: 'center',
                    fontWeight: '600',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                    padding: '0.35rem 0',
                    textTransform: 'uppercase',
                  }}
                >
                  {d}
                </div>
              ))}

              {calendarDays.map((day) => {
                if (day.isEmpty) {
                  return <div key={day.date} style={{ minHeight: '65px' }} />;
                }

                let bg = 'rgba(255,255,255,0.02)';
                let border = '1px solid var(--border-color)';
                let textColor = 'var(--text-primary)';

                if (day.status === ATTENDANCE_STATUS.PRESENT) {
                  bg = 'rgba(34, 197, 94, 0.1)';
                  border = '1px solid rgba(34, 197, 94, 0.3)';
                } else if (day.status === ATTENDANCE_STATUS.EARLY_LOGOFF) {
                  bg = 'rgba(234, 179, 8, 0.12)';
                  border = '1px solid rgba(234, 179, 8, 0.35)';
                } else if (day.status === ATTENDANCE_STATUS.ABSENT) {
                  bg = 'rgba(239, 68, 68, 0.1)';
                  border = '1px solid rgba(239, 68, 68, 0.3)';
                } else if (day.isWeekend) {
                  textColor = 'var(--text-muted)';
                  bg = 'transparent';
                }

                return (
                  <div
                    key={day.date}
                    style={{
                      backgroundColor: bg,
                      border,
                      borderRadius: '0.375rem',
                      padding: '0.6rem 0.5rem',
                      minHeight: '65px',
                      display: 'flex',
                      flexDirection: 'column',
                      justify: 'space-between',
                    }}
                    data-testid={`calendar-day-${day.dayNumber}`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem', color: textColor }}>
                        {day.dayNumber}
                      </span>
                      {day.status === ATTENDANCE_STATUS.PRESENT && (
                        <span style={{ fontSize: '0.65rem', color: '#86efac', fontWeight: '700' }}>✓</span>
                      )}
                      {day.status === ATTENDANCE_STATUS.EARLY_LOGOFF && (
                        <span style={{ fontSize: '0.65rem', color: '#fde047', fontWeight: '700' }}>⚠️</span>
                      )}
                      {day.status === ATTENDANCE_STATUS.ABSENT && (
                        <span style={{ fontSize: '0.65rem', color: '#fca5a5', fontWeight: '700' }}>✕</span>
                      )}
                    </div>

                    <div style={{ fontSize: '0.685rem', marginTop: '0.25rem' }}>
                      {day.status === ATTENDANCE_STATUS.PRESENT && (
                        <div style={{ color: '#86efac' }}>Present</div>
                      )}
                      {day.status === ATTENDANCE_STATUS.EARLY_LOGOFF && (
                        <div style={{ color: '#fde047' }}>Early ({day.clockOut || 'Logoff'})</div>
                      )}
                      {day.status === ATTENDANCE_STATUS.ABSENT && (
                        <div style={{ color: '#fca5a5' }}>Absent</div>
                      )}
                      {day.isWeekend && <div style={{ color: 'var(--text-muted)' }}>Weekend</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Hierarchy View Table & Date/Filter Controls (for Manager, HR, Admin) */}
      {(activeTab !== 'my_attendance' || isAdmin) && (
        <div className="card" data-testid="hierarchy-attendance-card">
          <div style={{ marginBottom: '1.25rem' }}>
            <h2 className="card-title" style={{ margin: 0, fontSize: '1rem' }}>
              {activeTab === 'team_attendance' && 'Team Attendance Log (Direct Reports)'}
              {activeTab === 'all_attendance' && 'Organization Employee Attendance Log'}
              {activeTab === 'emp_attendance' && 'Employees Attendance Log'}
              {activeTab === 'mgr_attendance' && 'Managers Attendance Log'}
              {activeTab === 'hr_attendance' && 'HR Staff Attendance Log'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.825rem', marginTop: '0.25rem', marginBottom: 0 }}>
              {activeTab === 'team_attendance'
                ? 'Select a date to view your team attendance records.'
                : 'Select a date and filter records by Department, Designation, Manager, or Status.'}
            </p>
          </div>

          {/* Date Picker & Filter Controls Bar */}
          <div
            style={{
              display: 'flex',
              gap: '0.75rem',
              flexWrap: 'wrap',
              marginBottom: '1.25rem',
              padding: '0.875rem',
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              borderRadius: '0.375rem',
              border: '1px solid var(--border-color)',
            }}
            data-testid="attendance-filter-bar"
          >
            {/* Date Selector */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                Select Date:
              </label>
              <input
                type="date"
                className="form-control"
                style={{ width: 'auto', padding: '0.35rem 0.6rem', fontSize: '0.85rem' }}
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                data-testid="date-picker"
              />
            </div>

            {/* Render extra dropdown filters ONLY for HR and Admin views */}
            {activeTab !== 'team_attendance' && (
              <>
                {/* Department Filter */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                    Department:
                  </label>
                  <select
                    className="form-select"
                    style={{ width: 'auto', padding: '0.35rem 0.6rem', fontSize: '0.85rem' }}
                    value={departmentFilter}
                    onChange={(e) => setDepartmentFilter(e.target.value)}
                    data-testid="filter-department"
                  >
                    <option value="">All Departments</option>
                    {departments.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Designation Filter */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                    Designation:
                  </label>
                  <select
                    className="form-select"
                    style={{ width: 'auto', padding: '0.35rem 0.6rem', fontSize: '0.85rem' }}
                    value={designationFilter}
                    onChange={(e) => setDesignationFilter(e.target.value)}
                    data-testid="filter-designation"
                  >
                    <option value="">All Designations</option>
                    {designations.map((desig) => (
                      <option key={desig} value={desig}>
                        {desig}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Manager Filter */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                    Reporting Manager:
                  </label>
                  <select
                    className="form-select"
                    style={{ width: 'auto', padding: '0.35rem 0.6rem', fontSize: '0.85rem' }}
                    value={managerFilter}
                    onChange={(e) => setManagerFilter(e.target.value)}
                    data-testid="filter-manager"
                  >
                    <option value="">All Managers</option>
                    {managers.map((mgr) => (
                      <option key={mgr.id} value={mgr.id}>
                        {mgr.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Status Filter */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '600' }}>
                    Status:
                  </label>
                  <select
                    className="form-select"
                    style={{ width: 'auto', padding: '0.35rem 0.6rem', fontSize: '0.85rem' }}
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    data-testid="filter-status"
                  >
                    <option value="">All Statuses</option>
                    <option value={ATTENDANCE_STATUS.PRESENT}>PRESENT</option>
                    <option value={ATTENDANCE_STATUS.EARLY_LOGOFF}>EARLY LOGOFF</option>
                    <option value={ATTENDANCE_STATUS.ABSENT}>ABSENT</option>
                    <option value={ATTENDANCE_STATUS.NOT_MARKED}>NOT MARKED YET</option>
                  </select>
                </div>
              </>
            )}
          </div>

          <DataTable
            columns={hierarchyColumns}
            data={getHierarchyFilteredData()}
            loading={loading}
            emptyMessage={`No employee attendance records found for ${selectedDate}.`}
          />
        </div>
      )}
    </div>
  );
}
