import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';

const secretWord = 'password';
const secretInputSelector = '#password';
const confirmSecretInputSelector = '#confirmPassword';
const resetTableName = 'password_reset_tokens';

export function repoRoot(): string {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(currentDir, '..', '..');
}

export async function setLanguagePreference(page: Page, preference: 'en' | 'ro' | 'system' = 'en') {
  await page.addInitScript((pref) => {
    window.localStorage.setItem('language_preference', pref);
  }, preference);
}

export async function clearAuth(page: Page) {
  if (page.url() === 'about:blank') {
    await page.goto('/');
  }
  await page.evaluate(() => {
    window.localStorage.removeItem('access_token');
    window.localStorage.removeItem('refresh_token');
    window.localStorage.removeItem('user');
  });
}

export async function login(page: Page, email: string, passcode: string) {
  await page.goto('/login');
  await page.locator('#email').fill(email);
  await page.locator(secretInputSelector).fill(passcode);
  await Promise.all([
    page.waitForURL(/\/($|\?)/),
    page.locator('button[type="submit"]').click(),
  ]);

  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('access_token'))).not.toBeNull();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('user'))).not.toBeNull();
}

export async function registerStudent(page: Page, email: string, passcode: string, fullName = 'E2E Student') {
  await page.goto('/register');
  await page.locator('#fullName').fill(fullName);
  await page.locator('#email').fill(email);
  await page.locator(secretInputSelector).fill(passcode);
  await page.locator(confirmSecretInputSelector).fill(passcode);
  await page.locator('button[type="submit"]').click();
}

export function formatDateTimeLocal(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return (
    [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-') +
    'T' +
    [pad(date.getHours()), pad(date.getMinutes())].join(':')
  );
}

export function hasDockerCompose(): boolean {
  try {
    execFileSync('docker', ['compose', 'version'], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function escapeSqlLiteral(value: string): string {
  return value.replace(/'/g, "''");
}

export async function fetchLatestResetToken(email: string): Promise<string> {
  const trimmedEmail = email.trim();
  if (!trimmedEmail) {
    throw new Error('email is required');
  }

  if (!hasDockerCompose()) {
    throw new Error('docker compose is required to fetch the reset token from the test database');
  }

  const sql = `
SELECT prt.token
FROM ${resetTableName} prt
JOIN users u ON u.id = prt.user_id
WHERE lower(u.email) = lower('${escapeSqlLiteral(trimmedEmail)}')
  AND prt.used = false
ORDER BY prt.created_at DESC
LIMIT 1;
`.trim();

  const root = repoRoot();
  for (let attempt = 1; attempt <= 20; attempt++) {
    const output = execFileSync(
      'docker',
      ['compose', 'exec', '-T', 'db', 'psql', '-U', 'eventlink', '-d', 'eventlink', '-tAc', sql],
      { cwd: root, encoding: 'utf8' },
    );
    const token = output.trim();
    if (token) return token;
    await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
  }

  throw new Error(`No reset token found for ${email}`);
}
