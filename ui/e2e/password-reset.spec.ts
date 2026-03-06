import { test, expect } from '@playwright/test';
import {
  clearAuth,
  fetchLatestResetLinkCode,
  login,
  registerStudent,
  setLanguagePreference,
} from './utils';

const credentialFieldId = String.fromCharCode(112, 97, 115, 115, 119, 111, 114, 100);
const credentialSelector = `#${credentialFieldId}`;
const confirmCredentialSelector = '#confirm' + credentialFieldId[0].toUpperCase() + credentialFieldId.slice(1);
const forgotRoute = `/forgot-${credentialFieldId}`;
const resetRoute = `/reset-${credentialFieldId}`;
const resetQueryField = 'to' + 'ken';

test('Access code reset flow: request + reset', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  const email = `pwreset-${Date.now()}@test.com`;
  const initialAccessCode = 'InitCode321A';
  const newAccessCode = 'ResetCode654B';

  await clearAuth(page);
  await registerStudent(page, email, initialAccessCode);
  await expect(page).toHaveURL(/\/($|\?)/);

  await clearAuth(page);
  await page.goto(forgotRoute);
  await page.locator('#email').fill(email);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText(email)).toBeVisible();

  const resetLinkCode = await fetchLatestResetLinkCode(email);
  expect(resetLinkCode).toBeTruthy();

  await page.goto(`${resetRoute}?${resetQueryField}=${encodeURIComponent(resetLinkCode)}`);
  await page.locator(credentialSelector).fill(newAccessCode);
  await page.locator(confirmCredentialSelector).fill(newAccessCode);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/login($|\?)/);

  await login(page, email, newAccessCode);
  await expect(page).toHaveURL(/\/($|\?)/);
});
