export function validateEmployeeForm(values, isCreate = false) {
  const errors = {};

  if (!values.name || !values.name.trim()) {
    errors.name = 'Name is required.';
  }

  if (!values.email || !values.email.trim()) {
    errors.email = 'Email is required.';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = 'Valid email is required.';
  }

  if (!values.department || !values.department.trim()) {
    errors.department = 'Department is required.';
  }

  if (!values.designation || !values.designation.trim()) {
    errors.designation = 'Designation is required.';
  }

  if (isCreate) {
    if (!values.initial_password || values.initial_password.length < 8) {
      errors.initial_password = 'Password must be at least 8 characters.';
    }
    const salaryNum = Number(values.monthly_salary);
    if (isNaN(salaryNum) || salaryNum <= 0) {
      errors.monthly_salary = 'Monthly salary must be a positive number.';
    }
  }

  if (values.id && values.manager_id && values.id === values.manager_id) {
    errors.manager_id = 'Employee cannot be their own manager.';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
