import { formatPrice, formatPricePerM2, formatArea, formatRelativeDate, truncate } from './utils';

describe('utils', () => {
  test('formatPrice', () => {
    expect(formatPrice(1_500_000_000)).toBe('1.5 tỷ');
    expect(formatPrice(2_000_000)).toBe('2 triệu');
    expect(formatPrice(500_000)).toBe('500,000 đ');
    expect(formatPrice(null)).toBe('Thỏa thuận');
  });

  test('formatPricePerM2', () => {
    expect(formatPricePerM2(25_000_000)).toBe('25.0 tr/m²');
    expect(formatPricePerM2(null)).toBe('N/A');
  });

  test('formatArea', () => {
    expect(formatArea(80)).toBe('80m²');
    expect(formatArea(null)).toBe('N/A');
  });

  test('formatRelativeDate', () => {
    const now = new Date();
    expect(formatRelativeDate(now.toISOString())).toBe('Hôm nay');
    const yesterday = new Date(now.getTime() - 24*60*60*1000);
    expect(formatRelativeDate(yesterday.toISOString())).toBe('Hôm qua');
  });

  test('truncate', () => {
    expect(truncate('abcdef', 3)).toBe('abc...');
    expect(truncate('abc', 10)).toBe('abc');
    expect(truncate('', 5)).toBe('');
  });
});
