import { ROLES } from './permissions.js';

export function leaveActions(user, leave) {
  if (!user || !leave) {
    return { canApprove: false, canReject: false, canCancel: false };
  }

  const { id: userId, role } = user;
  const isOwnLeave = userId === leave.employee_id;
  const isManagerOfLeave = leave.manager_id && leave.manager_id === userId;

  const isManagementRole = [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER].includes(role);
  const isAuthorizedManager = role === ROLES.MANAGER ? isManagerOfLeave : isManagementRole;

  // Approve & Reject rules:
  // - Status must be PENDING
  // - Role must be MANAGER, HR, or ADMIN
  // - A MANAGER can only act if leave.manager_id === user.id
  // - NOBODY can approve/reject their own leave
  const isPending = leave.status === 'PENDING';
  const canDecide = isPending && isAuthorizedManager && !isOwnLeave;

  const canApprove = canDecide;
  const canReject = canDecide;

  // Cancel rules:
  // - Status must be PENDING or APPROVED
  // - User must be the leave owner OR role must be HR / ADMIN
  const isCancelableStatus = ['PENDING', 'APPROVED'].includes(leave.status);
  const isOwnerOrAdminHR = isOwnLeave || [ROLES.ADMIN, ROLES.HR].includes(role);
  const canCancel = isCancelableStatus && isOwnerOrAdminHR;

  return {
    canApprove,
    canReject,
    canCancel,
  };
}

export function canCreateFor(user, targetEmployeeId) {
  if (!user || !targetEmployeeId) return false;
  if ([ROLES.ADMIN, ROLES.HR].includes(user.role)) return true;
  return user.id === targetEmployeeId;
}
