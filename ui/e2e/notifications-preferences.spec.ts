import { expect, test } from '@playwright/test';
import { clearAuth, login, setLanguagePreference } from './utils';

const STUDENT = { email: 'student@test.com', password: 'test123' };
const ADMIN = { email: 'admin@test.com', password: 'test123' };

test('notifications preferences + admin enqueue (digest + filling-fast)', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  // Student enables notification preferences.
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.goto('/profile');
  await expect(page).toHaveURL(/\/profile($|\?)/);

  const digestRow = page.getByText('Weekly digest').locator('..').locator('..');
  const digestCheckbox = digestRow.getByRole('checkbox');
  if ((await digestCheckbox.getAttribute('aria-checked')) !== 'true') {
    await digestCheckbox.click();
  }
  await expect(digestCheckbox).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByText('Preferences saved').first()).toBeVisible();

  const fillingFastRow = page.getByText('"Filling fast" alerts').locator('..').locator('..');
  const fillingFastCheckbox = fillingFastRow.getByRole('checkbox');
  if ((await fillingFastCheckbox.getAttribute('aria-checked')) !== 'true') {
    await fillingFastCheckbox.click();
  }
  await expect(fillingFastCheckbox).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByText('Preferences saved').first()).toBeVisible();

  await page.reload();
  await expect(page.getByText('Weekly digest').locator('..').locator('..').getByRole('checkbox')).toHaveAttribute(
    'aria-checked',
    'true',
  );
  await expect(
    page.getByText('"Filling fast" alerts').locator('..').locator('..').getByRole('checkbox'),
  ).toHaveAttribute('aria-checked', 'true');

  // Admin triggers digest + filling-fast enqueue actions.
  await clearAuth(page);
  await login(page, ADMIN.email, ADMIN.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.goto('/admin');
  await expect(page).toHaveURL(/\/admin($|\?)/);

  await page.getByRole('button', { name: 'Digest' }).click();
  await expect(page.getByText('Digest queued').first()).toBeVisible();

  await page.getByRole('button', { name: 'Filling-fast' }).click();
  await expect(page.getByText('Alerts queued').first()).toBeVisible();
});

