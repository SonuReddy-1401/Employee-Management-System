import React from 'react';

export function FormField({ label, error, required, children, id }) {
  return (
    <div className="form-group">
      {label && (
        <label className="form-label" htmlFor={id}>
          {label} {required && <span style={{ color: 'var(--accent-danger)' }}>*</span>}
        </label>
      )}
      {children}
      {error && <div className="form-error-text">{error}</div>}
    </div>
  );
}
