import { test, expect } from '@playwright/test';
import { clearAuth, formatDateTimeLocal, login, setLanguagePreference } from './utils';

const ORGANIZER = { email: 'organizer@test.com', password: 'test123' };
const STUDENT = { email: 'student@test.com', password: 'test123' };
const ADMIN = { email: 'admin@test.com', password: 'test123' };

test('organizer: duplicate event + soft-delete + admin restore', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  // Organizer creates an event (published by default)
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  const title = `E2E Clone Soft Delete ${Date.now()}`;

  await page.getByRole('link', { name: 'New Event' }).click();
  await expect(page).toHaveURL(/\/organizer\/events\/new$/);

  await page.locator('#title').fill(title);
  await page.locator('#description').fill('Clone + soft-delete/restore E2E event.');
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

  const eventId = Number(new URL(page.url()).pathname.split('/').pop());
  expect(eventId).toBeGreaterThan(0);

  // Organizer duplicates the event and lands on the edit page for the clone.
  await page.getByRole('button', { name: 'Duplicate event' }).click();
  await expect(page).toHaveURL(/\/organizer\/events\/\d+\/edit$/);

  const cloneId = Number(new URL(page.url()).pathname.split('/').at(-2));
  expect(cloneId).toBeGreaterThan(0);
  expect(cloneId).not.toBe(eventId);

  const cloneTitle = `E2E Clone Copy ${Date.now()}`;
  await expect(page.locator('#title')).toBeVisible();
  await page.locator('#title').fill(cloneTitle);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/organizer($|\?)/);

  // Organizer soft-deletes the original event from their dashboard.
  const originalRow = page.locator('tbody tr', { hasText: title });
  await expect(originalRow).toBeVisible();

  await originalRow.locator('button[aria-haspopup="menu"]').click();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('menuitem', { name: 'Delete' }).click();
  await expect(originalRow).toHaveCount(0);

  // Student should no longer find the event in the public list.
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);
  await page.getByPlaceholder('Search events...').fill(title);
  await expect(page.getByRole('heading', { name: title })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'No events found' })).toBeVisible();

  // Admin restores the deleted event.
  await clearAuth(page);
  await login(page, ADMIN.email, ADMIN.password);

  await page.goto('/admin');
  await expect(page).toHaveURL(/\/admin($|\?)/);

  await page.getByRole('tab', { name: 'Events' }).click();
  const eventsPanel = page.locator('[role="tabpanel"][data-state="active"]');
  await expect(eventsPanel.getByPlaceholder('title / owner')).toBeVisible();

  await eventsPanel.getByPlaceholder('title / owner').fill(title);
  await eventsPanel.getByText('Include deleted').locator('..').getByRole('checkbox').click();
  await eventsPanel.getByRole('button', { name: 'Apply' }).click();

  const deletedEventRow = eventsPanel.locator('tbody tr', { hasText: title });
  await expect(deletedEventRow).toBeVisible();
  await expect(deletedEventRow.getByText('deleted')).toBeVisible();
  await deletedEventRow.getByRole('button', { name: 'Restore' }).click();
  await expect(deletedEventRow.getByText('deleted')).toHaveCount(0);

  // Student should see the event again after restore.
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);
  await page.getByPlaceholder('Search events...').fill(title);
  await expect(page.getByRole('heading', { name: title }).first()).toBeVisible();
});

