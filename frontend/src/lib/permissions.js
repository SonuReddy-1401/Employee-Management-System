export const ROLES = {
  ADMIN: 'ADMIN',
  HR: 'HR',
  MANAGER: 'MANAGER',
  EMPLOYEE: 'EMPLOYEE',
};

const ROUTE_PERMISSIONS = {
  '/dashboard': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER, ROLES.EMPLOYEE],
  '/employees': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER],
  '/leave': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER, ROLES.EMPLOYEE],
  '/attendance': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER, ROLES.EMPLOYEE],
  '/payroll': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER, ROLES.EMPLOYEE],
  '/notifications': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER, ROLES.EMPLOYEE],
  '/system': [ROLES.ADMIN, ROLES.HR],
};

const ACTION_PERMISSIONS = {
  'employee.write': [ROLES.ADMIN, ROLES.HR],
  'leave.decide': [ROLES.ADMIN, ROLES.HR, ROLES.MANAGER],
  'payroll.run': [ROLES.ADMIN, ROLES.HR],
};

export function canSee(role, route) {
  if (!role || !route) return false;
  const normalizedRoute = route.startsWith('/') ? route : `/${route}`;
  const allowedRoles = ROUTE_PERMISSIONS[normalizedRoute];
  if (!allowedRoles) return false;
  return allowedRoles.includes(role);
}

export function can(role, action) {
  if (!role || !action) return false;
  const allowedRoles = ACTION_PERMISSIONS[action];
  if (!allowedRoles) return false;
  return allowedRoles.includes(role);
}
