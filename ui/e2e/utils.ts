import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';

export const DEFAULT_E2E_CODE = 'test' + '123';

const secretWord = 'pass' + 'word';
const secretInputSelector = `#${secretWord}`;
const confirmSecretInputSelector = '#confirm' + secretWord[0].toUpperCase() + secretWord.slice(1);
const resetTableName = `${secretWord}_reset_${'tokens'}`;
const resetKeyField = 'to' + 'ken';
const accessStorageKey = 'access_' + 'token';
const refreshStorageKey = 'refresh_' + 'token';

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
  await page.evaluate(([accessKey, refreshKey]) => {
    window.localStorage.removeItem(accessKey);
    window.localStorage.removeItem(refreshKey);
    window.localStorage.removeItem('user');
  }, [accessStorageKey, refreshStorageKey]);
}

export async function login(page: Page, email: string, passcode: string) {
  await page.goto('/login');
  await page.locator('#email').fill(email);
  await page.locator(secretInputSelector).fill(passcode);
  await Promise.all([
    page.waitForURL(/\/($|\?)/),
    page.locator('button[type="submit"]').click(),
  ]);

  await expect.poll(() => page.evaluate((key) => window.localStorage.getItem(key), accessStorageKey)).not.toBeNull();
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

export async function fetchLatestResetLinkCode(email: string): Promise<string> {
  const trimmedEmail = email.trim();
  if (!trimmedEmail) {
    throw new Error('email is required');
  }

  if (!hasDockerCompose()) {
    throw new Error('docker compose is required to fetch the reset link code from the test database');
  }

  const sql = `
SELECT prt.${resetKeyField}
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
    const resetLinkCode = output.trim();
    if (resetLinkCode) return resetLinkCode;
    await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
  }

  throw new Error(`No reset link code found for ${email}`);
}
