import { test, expect } from '@playwright/test';
import { clearAuth, formatDateTimeLocal, login, registerStudent, setLanguagePreference } from './utils';

const ADMIN = { email: 'admin@test.com', password: 'test123' };
const ORGANIZER = { email: 'organizer@test.com', password: 'test123' };

test('admin dashboard: user management + event moderation', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  // Create a user for admin management tests (avoid mutating shared seed accounts).
  const managedUserEmail = `e2e-admin-mgmt-${Date.now()}@test.com`;
  const managedUserPassword = 'Managed123';
  await clearAuth(page);
  await registerStudent(page, managedUserEmail, managedUserPassword, 'E2E Managed User');
  await expect(page).toHaveURL(/\/($|\?)/);

  // Create a flagged event (deterministic moderation flags).
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  const flaggedTitle = `E2E Moderation ${Date.now()}`;
  await page.getByRole('link', { name: 'New Event' }).click();
  await expect(page).toHaveURL(/\/organizer\/events\/new$/);

  await page.locator('#title').fill(flaggedTitle);
  await page
    .locator('#description')
    .fill('Please confirm your password at https://bit.ly/eventlink before joining.');
  await page.getByRole('combobox').first().click();
  await page.getByRole('option', { name: 'Workshop' }).click();

  const start = new Date();
  start.setDate(start.getDate() + 7);
  start.setHours(10, 0, 0, 0);
  const end = new Date(start);
  end.setHours(12, 0, 0, 0);

  await page.locator('#start_time').fill(formatDateTimeLocal(start));
  await page.locator('#end_time').fill(formatDateTimeLocal(end));
  await page.locator('#city').fill('Bucharest');
  await page.locator('#location').fill('Test venue');
  await page.locator('#max_seats').fill('10');

  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/events\/\d+$/);

  // Admin updates the user's role + active status.
  await clearAuth(page);
  await login(page, ADMIN.email, ADMIN.password);

  await page.goto('/admin');
  await expect(page).toHaveURL(/\/admin($|\?)/);

  await page.getByRole('tab', { name: 'Users' }).click();
  const usersPanel = page.locator('[role="tabpanel"][data-state="active"]');
  await expect(usersPanel.getByPlaceholder('email / name')).toBeVisible();

  await usersPanel.getByPlaceholder('email / name').fill(managedUserEmail);
  await usersPanel.getByRole('button', { name: 'Apply' }).click();

  const userRow = usersPanel.locator('tbody tr', { hasText: managedUserEmail });
  await expect(userRow).toBeVisible();

  const roleSelect = userRow.getByRole('combobox');
  await roleSelect.click();
  await page.getByRole('option', { name: 'Organizer' }).click();
  await expect(roleSelect).toHaveText(/Organizer/);

  const activeCheckbox = userRow.getByRole('checkbox').first();
  if ((await activeCheckbox.getAttribute('aria-checked')) !== 'false') {
    await activeCheckbox.click();
  }
  await expect(activeCheckbox).toHaveAttribute('aria-checked', 'false');

  // Admin reviews a flagged event.
  await page.getByRole('tab', { name: 'Events' }).click();
  const eventsPanel = page.locator('[role="tabpanel"][data-state="active"]');
  await expect(eventsPanel.getByPlaceholder('title / owner')).toBeVisible();

  await eventsPanel.getByPlaceholder('title / owner').fill(flaggedTitle);
  await eventsPanel.getByText('Flagged only').locator('..').getByRole('checkbox').click();
  await eventsPanel.getByRole('button', { name: 'Apply' }).click();

  const eventRow = eventsPanel.locator('tbody tr', { hasText: flaggedTitle });
  await expect(eventRow).toBeVisible();
  await expect(eventRow.getByText('Flagged')).toBeVisible();
  await eventRow.getByRole('button', { name: 'Mark reviewed' }).click();
  await expect(eventRow.getByText('Reviewed')).toBeVisible();
  await expect(eventRow.getByRole('button', { name: 'Mark reviewed' })).toHaveCount(0);
});
