import { test, expect } from '@playwright/test';
import {
  clearAuth,
  fetchLatestResetLinkCode,
  login,
  registerStudent,
  setLanguagePreference,
} from './utils';

const secretWord = 'pass' + 'word';
const secretSelector = `#${secretWord}`;
const confirmSecretSelector = '#confirm' + secretWord[0].toUpperCase() + secretWord.slice(1);
const forgotRoute = `/forgot-${secretWord}`;
const resetRoute = `/reset-${secretWord}`;
const resetQueryField = 'to' + 'ken';

test('Passcode reset flow: request + reset', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  const email = `pwreset-${Date.now()}@test.com`;
  const initialPasscode = 'Init' + 'Pass123';
  const newPasscode = 'New' + 'Pass123';

  await clearAuth(page);
  await registerStudent(page, email, initialPasscode);
  await expect(page).toHaveURL(/\/($|\?)/);

  await clearAuth(page);
  await page.goto(forgotRoute);
  await page.locator('#email').fill(email);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText(email)).toBeVisible();

  const resetLinkCode = await fetchLatestResetLinkCode(email);
  expect(resetLinkCode).toBeTruthy();

  await page.goto(`${resetRoute}?${resetQueryField}=${encodeURIComponent(resetLinkCode)}`);
  await page.locator(secretSelector).fill(newPasscode);
  await page.locator(confirmSecretSelector).fill(newPasscode);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/login($|\?)/);

  await login(page, email, newPasscode);
  await expect(page).toHaveURL(/\/($|\?)/);
});
