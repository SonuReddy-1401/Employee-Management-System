import React from 'react';

export function EmptyState({ message = 'No data available.' }) {
  return (
    <div className="empty-state" data-testid="empty-state">
      <div className="empty-state-text">{message}</div>
    </div>
  );
}
