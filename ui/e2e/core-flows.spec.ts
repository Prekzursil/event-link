import { test, expect, type Page } from '@playwright/test';

const ORGANIZER = { email: 'organizer@test.com', password: 'test123' };
const STUDENT = { email: 'student@test.com', password: 'test123' };

async function setLanguageToEnglish(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('language_preference', 'en');
  });
}

async function clearAuth(page: Page) {
  if (page.url() === 'about:blank') {
    await page.goto('/');
  }
  await page.evaluate(() => {
    window.localStorage.removeItem('access_token');
    window.localStorage.removeItem('refresh_token');
    window.localStorage.removeItem('user');
  });
}

async function login(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/($|\\?)/);
}

function formatDateTimeLocal(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join('-') + 'T' + [pad(date.getHours()), pad(date.getMinutes())].join(':');
}

test('core flows: organizer create/edit, student register, organizer attendance, student unregister', async ({ page }) => {
  await setLanguageToEnglish(page);

  // Organizer creates an event
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);

  const baseTitle = `E2E Workshop ${Date.now()}`;
  const updatedTitle = `${baseTitle} (edited)`;

  await page.goto('/organizer/events/new');
  await page.locator('#title').fill(baseTitle);
  await page.locator('#description').fill('Playwright end-to-end test event.');

  // Category select (first combobox)
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

  const createdEventId = Number(new URL(page.url()).pathname.split('/').pop());
  expect(createdEventId).toBeGreaterThan(0);

  // Organizer edits the event title
  await page.getByRole('link', { name: 'Edit event' }).click();
  await expect(page).toHaveURL(new RegExp(`/organizer/events/${createdEventId}/edit$`));
  await page.locator('#title').fill(updatedTitle);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/organizer($|\?)/);

  // Verify the updated title is visible on the event page
  await page.goto(`/events/${createdEventId}`);
  await expect(page.getByRole('heading', { name: updatedTitle })).toBeVisible();

  // Student registers for the event
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await page.goto(`/events/${createdEventId}`);
  await page.getByRole('button', { name: 'Register for event' }).click();
  await expect(page.getByRole('button', { name: 'Unregister' })).toBeVisible();

  // Organizer marks attendance for the student
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await page.goto(`/organizer/events/${createdEventId}/participants`);
  await expect(page.getByRole('link', { name: STUDENT.email })).toBeVisible();

  const participantRow = page.locator('tr', { hasText: STUDENT.email });
  const attendedToggle = participantRow.getByRole('checkbox').first();
  if ((await attendedToggle.getAttribute('aria-checked')) !== 'true') {
    await attendedToggle.click();
  }
  await expect(attendedToggle).toHaveAttribute('aria-checked', 'true');

  // Student unregisters
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await page.goto(`/events/${createdEventId}`);
  await page.getByRole('button', { name: 'Unregister' }).click();
  await expect(page.getByRole('button', { name: 'Register for event' })).toBeVisible();
});
