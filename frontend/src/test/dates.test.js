import { describe, it, expect } from 'vitest';
import { countWeekdays, validateLeaveRange } from '../lib/dates.js';

describe('dates utility', () => {
  it('counts weekdays correctly for a normal Mon-Fri week', () => {
    // 2026-03-02 (Mon) to 2026-03-06 (Fri)
    expect(countWeekdays('2026-03-02', '2026-03-06')).toBe(5);
  });

  it('returns 0 for weekend-only range', () => {
    // 2026-03-07 (Sat) to 2026-03-08 (Sun)
    expect(countWeekdays('2026-03-07', '2026-03-08')).toBe(0);
  });

  it('counts a single weekday as 1', () => {
    // 2026-03-04 (Wed)
    expect(countWeekdays('2026-03-04', '2026-03-04')).toBe(1);
  });

  it('counts Friday to Monday as 2 weekdays (Fri, Mon)', () => {
    // 2026-03-06 (Fri) to 2026-03-09 (Mon)
    expect(countWeekdays('2026-03-06', '2026-03-09')).toBe(2);
  });

  it('handles leap year February date calculations correctly', () => {
    // 2024-02-28 (Wed) to 2024-03-01 (Fri) -> Wed, Thu(29th), Fri = 3 weekdays
    expect(countWeekdays('2024-02-28', '2024-03-01')).toBe(3);
  });

  it('rejects cross calendar year ranges in validateLeaveRange', () => {
    // Dec 31 to Jan 1
    const err = validateLeaveRange('2025-12-31', '2026-01-01');
    expect(err).toBe('Leave request cannot span multiple calendar years.');
  });

  it('validates leave range rules', () => {
    expect(validateLeaveRange('', '2026-03-05')).toBe('Start date and end date are required.');
    expect(validateLeaveRange('2026-03-05', '2026-03-01')).toBe('End date cannot be before start date.');
    expect(validateLeaveRange('2026-03-07', '2026-03-08')).toBe('Leave range contains no weekdays (Mon-Fri).');
    expect(validateLeaveRange('2026-03-02', '2026-03-06')).toBeNull();
  });
});
