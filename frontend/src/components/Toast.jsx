import React from 'react';

export function Toast({ type = 'error', message }) {
  if (!message) return null;
  const className = `toast toast-${type}`;
  return <div className={className} data-testid={`toast-${type}`}>{message}</div>;
}
