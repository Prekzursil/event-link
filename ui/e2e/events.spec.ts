import { test, expect } from '@playwright/test';

const apiBase = process.env.E2E_API_URL;
const studentEmail = process.env.E2E_STUDENT_EMAIL;
const studentPassword = process.env.E2E_STUDENT_PASSWORD;
const organizerEmail = process.env.E2E_ORG_EMAIL;
const organizerPassword = process.env.E2E_ORG_PASSWORD;

async function createEvent(): Promise<number | null> {
  if (!apiBase || !organizerEmail || !organizerPassword) return null;
  const loginResp = await fetch(`${apiBase}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: organizerEmail, password: organizerPassword }),
  });
  if (!loginResp.ok) return null;
  const token = (await loginResp.json()).access_token as string;
  const start = new Date(Date.now() + 1000 * 60 * 60).toISOString();
  const payload = {
    title: 'E2E Playwright Event',
    description: 'Auto-created by Playwright smoke test',
    category: 'Test',
    start_time: start,
    end_time: null,
    location: 'Online',
    max_seats: 10,
    tags: ['e2e'],
  };
  const createResp = await fetch(`${apiBase}/api/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!createResp.ok) return null;
  const event = await createResp.json();
  return event.id as number;
}

test.describe('Events list', () => {
  test('loads event list hero and filters', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByLabel(/Caută/)).toBeVisible();
    await expect(page.getByLabel(/Categorie/)).toBeVisible();
  });
});

test.describe('Registration flow (optional)', () => {
  test.beforeEach(async function () {
    if (!apiBase || !studentEmail || !studentPassword || !organizerEmail || !organizerPassword) {
      test.skip(true, 'E2E_API_URL and user credentials are required for registration test');
    }
  });

  test('student can register and unregister for a fresh event', async ({ page }) => {
    const eventId = await createEvent();
    if (!eventId) test.skip(true, 'Event could not be prepared');

    const loginResp = await fetch(`${apiBase}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: studentEmail, password: studentPassword }),
    });
    expect(loginResp.ok).toBeTruthy();
    const { access_token: token } = await loginResp.json();

    await page.goto('/');
    await page.evaluate((jwt) => localStorage.setItem('access_token', jwt), token);
    await page.goto(`/events/${eventId}`);

    const registerBtn = page.getByRole('button', { name: /Înscrie-te|Register|Înscris/ });
    await expect(registerBtn).toBeVisible();
    await registerBtn.click();
    await expect(page.getByText(/Înscris|Registered/i)).toBeVisible();

    const unregisterBtn = page.getByRole('button', { name: /Retrage|Anuleaz/ }).first();
    if (await unregisterBtn.isVisible()) {
      await unregisterBtn.click();
      await expect(page.getByRole('button', { name: /Înscrie-te|Register/ })).toBeVisible();
    }
  });
});
