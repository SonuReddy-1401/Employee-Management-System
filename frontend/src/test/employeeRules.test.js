import { describe, it, expect } from 'vitest';
import { validateEmployeeForm } from '../lib/employeeRules.js';

describe('employeeRules utility', () => {
  it('validates a complete employee creation form', () => {
    const values = {
      name: 'Jane Doe',
      email: 'jane@ems.com',
      department: 'Engineering',
      designation: 'Senior Developer',
      initial_password: 'Password123!',
      monthly_salary: '5000',
    };
    const { isValid, errors } = validateEmployeeForm(values, true);
    expect(isValid).toBe(true);
    expect(errors).toEqual({});
  });

  it('detects missing required fields', () => {
    const values = {
      name: '',
      email: 'invalid-email',
      department: '',
      designation: '',
    };
    const { isValid, errors } = validateEmployeeForm(values, false);
    expect(isValid).toBe(false);
    expect(errors.name).toBe('Name is required.');
    expect(errors.email).toBe('Valid email is required.');
    expect(errors.department).toBe('Department is required.');
    expect(errors.designation).toBe('Designation is required.');
  });

  it('prevents an employee from being their own manager on edit', () => {
    const values = {
      id: 'emp-100',
      name: 'Bob',
      email: 'bob@ems.com',
      department: 'Sales',
      designation: 'Lead',
      manager_id: 'emp-100',
    };
    const { isValid, errors } = validateEmployeeForm(values, false);
    expect(isValid).toBe(false);
    expect(errors.manager_id).toBe('Employee cannot be their own manager.');
  });
});
