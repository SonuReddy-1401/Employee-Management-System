import { describe, it, expect } from 'vitest';
import { canSee, can, ROLES } from '../lib/permissions.js';

describe('permissions matrix', () => {
  const routes = ['/dashboard', '/employees', '/leave', '/payroll', '/notifications', '/system'];
  const actions = ['employee.write', 'leave.decide', 'payroll.run'];

  const expectedRouteAccess = {
    [ROLES.ADMIN]: ['/dashboard', '/employees', '/leave', '/payroll', '/notifications', '/system'],
    [ROLES.HR]: ['/dashboard', '/employees', '/leave', '/payroll', '/notifications', '/system'],
    [ROLES.MANAGER]: ['/dashboard', '/employees', '/leave', '/payroll', '/notifications'],
    [ROLES.EMPLOYEE]: ['/dashboard', '/leave', '/payroll', '/notifications'],
  };

  const expectedActionAccess = {
    [ROLES.ADMIN]: ['employee.write', 'leave.decide', 'payroll.run'],
    [ROLES.HR]: ['employee.write', 'leave.decide', 'payroll.run'],
    [ROLES.MANAGER]: ['leave.decide'],
    [ROLES.EMPLOYEE]: [],
  };

  Object.values(ROLES).forEach((role) => {
    describe(`Role: ${role}`, () => {
      routes.forEach((route) => {
        const shouldAccess = expectedRouteAccess[role].includes(route);
        it(`canSee(${role}, "${route}") returns ${shouldAccess}`, () => {
          expect(canSee(role, route)).toBe(shouldAccess);
        });
      });

      actions.forEach((action) => {
        const shouldPerform = expectedActionAccess[role].includes(action);
        it(`can(${role}, "${action}") returns ${shouldPerform}`, () => {
          expect(can(role, action)).toBe(shouldPerform);
        });
      });
    });
  });
});
