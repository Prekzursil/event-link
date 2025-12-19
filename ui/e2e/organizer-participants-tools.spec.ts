import { test, expect } from '@playwright/test';
import { clearAuth, formatDateTimeLocal, login, setLanguagePreference } from './utils';

const ORGANIZER = { email: 'organizer@test.com', password: 'test123' };
const STUDENT = { email: 'student@test.com', password: 'test123' };

test('organizer participants tools: attendance + CSV export + email', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  // Organizer creates an event
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  const title = `E2E Participants ${Date.now()}`;

  await page.getByRole('link', { name: 'New Event' }).click();
  await expect(page).toHaveURL(/\/organizer\/events\/new$/);
  await page.locator('#title').fill(title);
  await page.locator('#description').fill('Participants tools E2E event.');

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

  // Student registers
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.getByPlaceholder('Search events...').fill(title);
  const studentHeading = page.getByRole('heading', { name: title }).first();
  await expect(studentHeading).toBeVisible();
  await studentHeading.click();
  await page.getByRole('button', { name: 'Register for event' }).click();
  await expect(page.getByRole('button', { name: 'Unregister' })).toBeVisible();

  // Organizer checks participants tools
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.getByPlaceholder('Search events...').fill(title);
  const organizerHeading = page.getByRole('heading', { name: title }).first();
  await expect(organizerHeading).toBeVisible();
  await organizerHeading.click();
  await page.getByRole('link', { name: 'View participants' }).click();
  await expect(page).toHaveURL(new RegExp(`/organizer/events/${eventId}/participants$`));

  await expect(page.getByRole('link', { name: STUDENT.email })).toBeVisible();

  const participantRow = page.locator('tr', { hasText: STUDENT.email });
  const attendedToggle = participantRow.getByRole('checkbox').first();
  if ((await attendedToggle.getAttribute('aria-checked')) !== 'true') {
    await attendedToggle.click();
  }
  await expect(attendedToggle).toHaveAttribute('aria-checked', 'true');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^participants-.*\.csv$/);

  await page.getByRole('button', { name: 'Email participants' }).click();
  await page.locator('#email-subject').fill('E2E Participants email');
  await page.locator('#email-message').fill('Hello participants! This is an automated E2E test message.');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText('Email sent to 1 participants.')).toBeVisible();
});
