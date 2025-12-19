import { expect, test } from '@playwright/test';
import { clearAuth, formatDateTimeLocal, login, setLanguagePreference } from './utils';

const ORGANIZER = { email: 'organizer@test.com', password: 'test123' };
const STUDENT = { email: 'student@test.com', password: 'test123' };

test('personalization controls: hide tag + block organizer', async ({ page }) => {
  await setLanguagePreference(page, 'en');

  // Organizer creates a tagged event
  await clearAuth(page);
  await login(page, ORGANIZER.email, ORGANIZER.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  const title = `E2E Personalization ${Date.now()}`;
  const tagName = 'AI & ML';

  await page.getByRole('link', { name: 'New Event' }).click();
  await expect(page).toHaveURL(/\/organizer\/events\/new$/);
  await page.locator('#title').fill(title);
  await page.locator('#description').fill('Personalization controls E2E event.');
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

  const tagInput = page.getByPlaceholder('Add a tag');
  await tagInput.fill(tagName);
  await tagInput.press('Enter');

  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/events\/\d+$/);
  const eventId = Number(new URL(page.url()).pathname.split('/').pop());
  expect(eventId).toBeGreaterThan(0);

  // Student hides the tag from the event detail "Personalization" section
  await clearAuth(page);
  await login(page, STUDENT.email, STUDENT.password);
  await expect(page).toHaveURL(/\/($|\?)/);

  await page.goto(`/events/${eventId}`);
  await expect(page.getByRole('heading', { name: 'Personalization' })).toBeVisible();

  const hideTagSelect = page.getByRole('combobox').filter({ hasText: 'Pick a tag' }).first();
  await hideTagSelect.click();
  await page.getByRole('option', { name: tagName }).click();
  await page.getByRole('button', { name: 'Hide' }).click();
  await expect(page.getByText('Tag hidden').first()).toBeVisible();

  await page.getByRole('link', { name: 'Manage personalization settings' }).click();
  await expect(page).toHaveURL(/\/profile($|\?)/);

  const hiddenTagsSection = page.getByText('Hidden tags').locator('..');
  await expect(hiddenTagsSection.getByText(tagName)).toBeVisible();

  // Hidden-tag exclusions should remove the event from the feed/search results.
  await page.goto('/');
  await page.getByPlaceholder('Search events...').fill(title);
  await expect(page.getByRole('heading', { name: title })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'No events found' })).toBeVisible();

  // Unhide to validate the reverse flow (and keep the event available for the organizer-block test).
  await page.goto('/profile');
  const hiddenTagsSectionAfter = page.getByText('Hidden tags').locator('..');
  const unhideButtons = hiddenTagsSectionAfter.getByRole('button', { name: 'Unhide tag' });
  await expect(unhideButtons).toHaveCount(1);
  await unhideButtons.click();
  await expect(page.getByText('Tag unhidden').first()).toBeVisible();
  await expect(page.getByText("You don't have hidden tags.").first()).toBeVisible();

  await page.goto('/');
  await page.getByPlaceholder('Search events...').fill(title);
  await expect(page.getByRole('heading', { name: title }).first()).toBeVisible();

  // Block the organizer from the event detail page.
  await page.goto(`/events/${eventId}`);
  await expect(page.getByRole('heading', { name: 'Personalization' })).toBeVisible();
  await page.getByRole('button', { name: 'Block organizer' }).click();
  await expect(page.getByText('Organizer blocked').first()).toBeVisible();

  await page.getByRole('link', { name: 'Manage personalization settings' }).click();
  await expect(page).toHaveURL(/\/profile($|\?)/);

  const blockedSection = page.getByText('Blocked organizers').locator('..');
  await expect(blockedSection.getByText(ORGANIZER.email)).toBeVisible();
  await expect(blockedSection.getByRole('button', { name: 'Unblock' })).toBeVisible();

  // Blocked-organizer exclusions should remove the event from the feed/search results.
  await page.goto('/');
  await page.getByPlaceholder('Search events...').fill(title);
  await expect(page.getByRole('heading', { name: title })).toHaveCount(0);
});

