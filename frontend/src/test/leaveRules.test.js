import { describe, it, expect } from 'vitest';
import { leaveActions, canCreateFor } from '../lib/leaveRules.js';
import { ROLES } from '../lib/permissions.js';

describe('leaveRules utility', () => {
  const empUser = { id: 'emp-1', role: ROLES.EMPLOYEE };
  const mgrUser = { id: 'mgr-1', role: ROLES.MANAGER };
  const hrUser = { id: 'hr-1', role: ROLES.HR };
  const adminUser = { id: 'admin-1', role: ROLES.ADMIN };

  const pendingLeaveOther = {
    id: 'l-1',
    employee_id: 'emp-2',
    manager_id: 'mgr-1',
    status: 'PENDING',
  };

  const pendingLeaveOwn = {
    id: 'l-2',
    employee_id: 'emp-1',
    manager_id: 'mgr-1',
    status: 'PENDING',
  };

  const pendingLeaveOwnMgr = {
    id: 'l-3',
    employee_id: 'mgr-1',
    manager_id: 'mgr-2',
    status: 'PENDING',
  };

  const approvedLeaveOther = {
    id: 'l-4',
    employee_id: 'emp-2',
    manager_id: 'mgr-1',
    status: 'APPROVED',
  };

  const rejectedLeaveOther = {
    id: 'l-5',
    employee_id: 'emp-2',
    manager_id: 'mgr-1',
    status: 'REJECTED',
  };

  const cancelledLeaveOther = {
    id: 'l-6',
    employee_id: 'emp-2',
    manager_id: 'mgr-1',
    status: 'CANCELLED',
  };

  describe('leaveActions', () => {
    it('EMPLOYEE role actions', () => {
      // Cannot approve or reject any leave (own or other)
      expect(leaveActions(empUser, pendingLeaveOther)).toEqual({
        canApprove: false,
        canReject: false,
        canCancel: false,
      });
      // Can cancel own pending/approved leave
      expect(leaveActions(empUser, pendingLeaveOwn).canCancel).toBe(true);
    });

    it('MANAGER role actions', () => {
      // Can approve/reject pending leave of managed employee
      const res = leaveActions(mgrUser, pendingLeaveOther);
      expect(res.canApprove).toBe(true);
      expect(res.canReject).toBe(true);
      expect(res.canCancel).toBe(false);

      // Cannot approve/reject own leave even if manager
      const ownRes = leaveActions(mgrUser, pendingLeaveOwnMgr);
      expect(ownRes.canApprove).toBe(false);
      expect(ownRes.canReject).toBe(false);
      expect(ownRes.canCancel).toBe(true); // Can cancel own leave

      // Cannot approve leave managed by another manager
      const otherMgrUser = { id: 'mgr-99', role: ROLES.MANAGER };
      const otherRes = leaveActions(otherMgrUser, pendingLeaveOther);
      expect(otherRes.canApprove).toBe(false);
      expect(otherRes.canReject).toBe(false);
    });

    it('HR role actions', () => {
      const res = leaveActions(hrUser, pendingLeaveOther);
      expect(res.canApprove).toBe(true);
      expect(res.canReject).toBe(true);
      expect(res.canCancel).toBe(true);

      // Can cancel approved leave
      expect(leaveActions(hrUser, approvedLeaveOther).canCancel).toBe(true);
      // Cannot cancel terminal statuses
      expect(leaveActions(hrUser, rejectedLeaveOther).canCancel).toBe(false);
      expect(leaveActions(hrUser, cancelledLeaveOther).canCancel).toBe(false);
    });

    it('ADMIN role actions', () => {
      const res = leaveActions(adminUser, pendingLeaveOther);
      expect(res.canApprove).toBe(true);
      expect(res.canReject).toBe(true);
      expect(res.canCancel).toBe(true);
    });
  });

  describe('canCreateFor', () => {
    it('EMPLOYEE can create only for self', () => {
      expect(canCreateFor(empUser, 'emp-1')).toBe(true);
      expect(canCreateFor(empUser, 'emp-2')).toBe(false);
    });

    it('MANAGER can create only for self', () => {
      expect(canCreateFor(mgrUser, 'mgr-1')).toBe(true);
      expect(canCreateFor(mgrUser, 'emp-2')).toBe(false);
    });

    it('HR and ADMIN can create for anyone', () => {
      expect(canCreateFor(hrUser, 'emp-2')).toBe(true);
      expect(canCreateFor(adminUser, 'emp-2')).toBe(true);
    });
  });
});
