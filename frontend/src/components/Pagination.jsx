import React from 'react';

export function Pagination({ page = 1, pageSize = 20, total = 0, onPageChange, onPageSizeChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(total, page * pageSize);

  return (
    <div className="pagination-container" data-testid="pagination">
      <div className="pagination-info">
        Showing {startItem} - {endItem} of {total} items
      </div>
      <div className="pagination-controls">
        <label htmlFor="page-size-select" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Per page:
        </label>
        <select
          id="page-size-select"
          className="form-select"
          style={{ width: 'auto', padding: '0.25rem 0.5rem' }}
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
        >
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
        </select>

        <button
          className="btn btn-secondary"
          style={{ padding: '0.25rem 0.625rem' }}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <span style={{ fontSize: '0.875rem', padding: '0 0.5rem' }}>
          Page {page} of {totalPages}
        </span>
        <button
          className="btn btn-secondary"
          style={{ padding: '0.25rem 0.625rem' }}
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
