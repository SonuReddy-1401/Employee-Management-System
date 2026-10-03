function parseUTCDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return null;
  const parts = dateStr.split('-');
  if (parts.length !== 3) return null;
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10) - 1;
  const day = parseInt(parts[2], 10);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
  const d = new Date(Date.UTC(year, month, day));
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month || d.getUTCDate() !== day) {
    return null;
  }
  return d;
}

export function countWeekdays(startStr, endStr) {
  const start = parseUTCDate(startStr);
  const end = parseUTCDate(endStr);
  if (!start || !end || end < start) return 0;

  let count = 0;
  const current = new Date(start.getTime());

  while (current <= end) {
    const dayOfWeek = current.getUTCDay();
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      count++;
    }
    current.setUTCDate(current.getUTCDate() + 1);
  }

  return count;
}

export function validateLeaveRange(startStr, endStr) {
  if (!startStr || !endStr) {
    return 'Start date and end date are required.';
  }

  const start = parseUTCDate(startStr);
  const end = parseUTCDate(endStr);

  if (!start || !end) {
    return 'Invalid date format.';
  }

  if (end < start) {
    return 'End date cannot be before start date.';
  }

  if (start.getUTCFullYear() !== end.getUTCFullYear()) {
    return 'Leave request cannot span multiple calendar years.';
  }

  const weekdays = countWeekdays(startStr, endStr);
  if (weekdays === 0) {
    return 'Leave range contains no weekdays (Mon-Fri).';
  }

  return null;
}
