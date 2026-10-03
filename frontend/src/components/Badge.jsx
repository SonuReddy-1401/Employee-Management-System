import React from 'react';

export function Badge({ children, type = 'employee' }) {
  const badgeClass = `badge badge-${type.toLowerCase()}`;
  return <span className={badgeClass}>{children}</span>;
}
