import { test, expect } from '@playwright/test';
import { clearAuth, login, setLanguagePreference } from './utils';

const STUDENT = { email: 'student@test.com', password: 'test123' };

test('student profile: interests + academic fields', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.goto('/profile');
  await expect(page).toHaveURL(/\/profile($|\?)/);

  // Academic fields
  await page.locator('#city').fill('');
  await page.locator('#university').fill('Babes-Bolyai University of Cluj-Napoca');
  await expect(page.locator('#city')).toHaveValue('Cluj-Napoca');
  await page.locator('#faculty').fill('Facultatea de Matematică și Informatică');

  await page.getByTestId('study-level-trigger').click();
  await page.getByRole('option', { name: "Bachelor's" }).click();

  await page.getByTestId('study-year-trigger').click();
  await page.getByRole('option', { name: '2' }).click();

  // Interests
  const tagCheckbox = page.getByLabel('AI & ML');
  await tagCheckbox.click();
  await expect(tagCheckbox).toHaveAttribute('aria-checked', 'true');

  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Profile updated').first()).toBeVisible();

  await page.reload();
  await expect(page.locator('#city')).toHaveValue('Cluj-Napoca');
  await expect(page.locator('#university')).toHaveValue('Babes-Bolyai University of Cluj-Napoca');
  await expect(page.locator('#faculty')).toHaveValue('Facultatea de Matematică și Informatică');

  const tagCheckboxAfter = page.getByLabel('AI & ML');
  await expect(tagCheckboxAfter).toHaveAttribute('aria-checked', 'true');
});
