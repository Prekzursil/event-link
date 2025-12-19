import { test, expect } from '@playwright/test';
import { clearAuth, fetchLatestPasswordResetToken, login, registerStudent, setLanguagePreference } from './utils';

test('password reset flow: request + reset', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  const email = `pwreset-${Date.now()}@test.com`;
  const initialPassword = 'InitPass123';
  const newPassword = 'NewPass123';

  await clearAuth(page);
  await registerStudent(page, email, initialPassword);
  await expect(page).toHaveURL(/\/($|\?)/);

  await clearAuth(page);
  await page.goto('/forgot-password');
  await page.locator('#email').fill(email);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText(email)).toBeVisible();

  const token = await fetchLatestPasswordResetToken(email);
  expect(token).toBeTruthy();

  await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
  await page.locator('#password').fill(newPassword);
  await page.locator('#confirmPassword').fill(newPassword);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/login($|\?)/);

  await login(page, email, newPassword);
  await expect(page).toHaveURL(/\/($|\?)/);
});

