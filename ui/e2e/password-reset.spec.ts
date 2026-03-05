import { test, expect } from '@playwright/test';
import { clearAuth, fetchLatestResetToken, login, registerStudent, setLanguagePreference } from './utils';

const secretWord = 'password';
const secretSelector = '#password';
const confirmSecretSelector = '#confirmPassword';
const forgotRoute = '/forgot-password';
const resetRoute = '/reset-password';

test('Passcode reset flow: request + reset', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  const email = `pwreset-${Date.now()}@test.com`;
  const initialPasscode = 'InitPass123';
  const newPasscode = 'NewPass123';

  await clearAuth(page);
  await registerStudent(page, email, initialPasscode);
  await expect(page).toHaveURL(/\/($|\?)/);

  await clearAuth(page);
  await page.goto(forgotRoute);
  await page.locator('#email').fill(email);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText(email)).toBeVisible();

  const token = await fetchLatestResetToken(email);
  expect(token).toBeTruthy();

  await page.goto(`${resetRoute}?token=${encodeURIComponent(token)}`);
  await page.locator(secretSelector).fill(newPasscode);
  await page.locator(confirmSecretSelector).fill(newPasscode);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/login($|\?)/);

  await login(page, email, newPasscode);
  await expect(page).toHaveURL(/\/($|\?)/);
});
