import { describe, it, expect } from 'vitest';
import { formatMoney } from '../lib/money.js';

describe('money formatting utility', () => {
  it('formats string decimal inputs with 2 decimal places and thousands separators', () => {
    expect(formatMoney('20000.00')).toBe('20,000.00');
    expect(formatMoney('0.1')).toBe('0.10');
    expect(formatMoney('1234567.89')).toBe('1,234,567.89');
  });

  it('formats numeric inputs correctly', () => {
    expect(formatMoney(5000.5)).toBe('5,000.50');
    expect(formatMoney(0)).toBe('0.00');
  });

  it('handles null, undefined, empty string, or invalid inputs safely without throwing', () => {
    expect(formatMoney(null)).toBe('0.00');
    expect(formatMoney(undefined)).toBe('0.00');
    expect(formatMoney('')).toBe('0.00');
    expect(formatMoney('invalid')).toBe('0.00');
  });
});
