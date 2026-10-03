import React from 'react';

export function Badge({ children, type }) {
  if (!children) return null;
  const rawType = (type || children).toString().toLowerCase();
  const badgeClass = `badge badge-${rawType}`;
  return <span className={badgeClass}>{children}</span>;
}
