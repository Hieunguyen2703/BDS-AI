import { test, expect } from '@playwright/test';

test.describe('Listings', () => {
  test('can view listings page and see cards', async ({ page }) => {
    await page.goto('/listings');
    await page.waitForSelector('.card');
    const cards = await page.locator('.card').count();
    expect(cards).toBeGreaterThan(0);
  });

  test('can filter by district', async ({ page }) => {
    await page.goto('/listings');
    await page.click('text=Quận/Huyện');
    await page.click('text=Ba Đình');
    await page.waitForTimeout(1000);
    const cards = await page.locator('.card').count();
    expect(cards).toBeGreaterThan(0);
  });
});
