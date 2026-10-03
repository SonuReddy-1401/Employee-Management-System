import React from 'react';
import { Spinner } from './Spinner.jsx';
import { EmptyState } from './EmptyState.jsx';

export function DataTable({ columns, data, loading, onRowClick, emptyMessage = 'No records found.' }) {
  return (
    <div className="table-container" data-testid="data-table">
      {loading && (
        <div className="table-loading-overlay">
          <Spinner />
        </div>
      )}
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key || col.header}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {!loading && (!data || data.length === 0) ? (
            <tr>
              <td colSpan={columns.length}>
                <EmptyState message={emptyMessage} />
              </td>
            </tr>
          ) : (
            data.map((row, idx) => (
              <tr
                key={row.id || idx}
                onClick={() => onRowClick && onRowClick(row)}
                className={onRowClick ? 'clickable-row' : ''}
              >
                {columns.map((col) => (
                  <td key={col.key || col.header}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
