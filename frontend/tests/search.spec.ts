import { test, expect } from '@playwright/test';

test.describe('Search', () => {
  test('can search for listings and see results', async ({ page }) => {
    await page.goto('/search');
    await page.fill('input[type="text"]', 'nhà riêng Cầu Giấy dưới 5 tỷ');
    await page.click('button[type="submit"]');
    await page.waitForSelector('h2:has-text("Kết quả tìm kiếm")');
    const results = await page.locator('.grid .card').count();
    expect(results).toBeGreaterThan(0);
  });
});
