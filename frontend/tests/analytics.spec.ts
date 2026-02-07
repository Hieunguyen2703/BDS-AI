import { test, expect } from '@playwright/test';

test.describe('Analytics', () => {
  test('can view analytics page and see charts', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForSelector('h1:has-text("Phân tích thị trường")');
    await page.waitForSelector('canvas');
    const charts = await page.locator('canvas').count();
    expect(charts).toBeGreaterThan(0);
  });
});
