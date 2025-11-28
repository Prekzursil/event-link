import { test, expect } from '@playwright/test';

test.describe('Auth screens', () => {
  test('login page renders', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/parol|password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /autentificare|login/i })).toBeVisible();
  });

  test('register page renders', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/parol|password/i)).toBeVisible();
    await expect(page.getByLabel(/confirm/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /creează cont|create account/i })).toBeVisible();
  });
});
