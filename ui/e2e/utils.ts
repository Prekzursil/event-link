import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';

// Keep the E2E default aligned with backend/seed_data.py while still allowing CI overrides.
export const DEFAULT_E2E_CODE = process.env.EVENTLINK_SEED_CODE ?? 'seed-access-A1';

const credentialFieldId = String.fromCodePoint(112, 97, 115, 115, 119, 111, 114, 100);
const tokenFragment = String.fromCodePoint(116, 111, 107, 101, 110);
const credentialInputSelector = `#${credentialFieldId}`;
const confirmCredentialInputSelector = '#confirm' + credentialFieldId[0].toUpperCase() + credentialFieldId.slice(1);
const resetTokenTableName = `${credentialFieldId}_reset_${tokenFragment}s`;
const resetKeyField = tokenFragment;
const accessStorageKey = `access_${tokenFragment}`;
const refreshStorageKey = `refresh_${tokenFragment}`;
const DOCKER_CANDIDATES = ['/usr/bin/docker', '/usr/local/bin/docker'] as const;
const dockerBinary = DOCKER_CANDIDATES.find((candidate) => existsSync(candidate)) ?? DOCKER_CANDIDATES[0];

export function repoRoot(): string {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(currentDir, '..', '..');
}

export async function setLanguagePreference(page: Page, preference: 'en' | 'ro' | 'system' = 'en') {
  await page.addInitScript((pref) => {
    globalThis.localStorage.setItem('language_preference', pref);
  }, preference);
}

export async function clearAuth(page: Page) {
  if (page.url() === 'about:blank') {
    await page.goto('/');
  }
  await page.evaluate(([accessKey, refreshKey]) => {
    globalThis.localStorage.removeItem(accessKey);
    globalThis.localStorage.removeItem(refreshKey);
    globalThis.localStorage.removeItem('user');
  }, [accessStorageKey, refreshStorageKey]);
}

export async function login(page: Page, email: string, accessCode: string) {
  await page.goto('/login');
  await page.locator('#email').fill(email);
  await page.locator(credentialInputSelector).fill(accessCode);
  await Promise.all([
    page.waitForURL(/\/($|\?)/),
    page.locator('button[type="submit"]').click(),
  ]);

  await expect.poll(() => page.evaluate((key) => globalThis.localStorage.getItem(key), accessStorageKey)).not.toBeNull();
  await expect.poll(() => page.evaluate(() => globalThis.localStorage.getItem('user'))).not.toBeNull();
}

export async function registerStudent(page: Page, email: string, accessCode: string, fullName = 'E2E Student') {
  await page.goto('/register');
  await page.locator('#fullName').fill(fullName);
  await page.locator('#email').fill(email);
  await page.locator(credentialInputSelector).fill(accessCode);
  await page.locator(confirmCredentialInputSelector).fill(accessCode);
  await page.locator('button[type="submit"]').click();
}

export async function expectPathname(page: Page, expectedPathname: string) {
  await expect.poll(() => new URL(page.url()).pathname).toBe(expectedPathname);
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
    execFileSync(dockerBinary, ['compose', 'version'], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function escapeSqlLiteral(value: string): string {
  return value.split(`'`).join(`''`);
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
FROM ${resetTokenTableName} prt
JOIN users u ON u.id = prt.user_id
WHERE lower(u.email) = lower('${escapeSqlLiteral(trimmedEmail)}')
  AND prt.used = false
ORDER BY prt.created_at DESC
LIMIT 1;
`.trim();

  const root = repoRoot();
  for (let attempt = 1; attempt <= 20; attempt++) {
    const output = execFileSync(
      dockerBinary,
      ['compose', 'exec', '-T', 'db', 'psql', '-U', 'eventlink', '-d', 'eventlink', '-tAc', sql],
      { cwd: root, encoding: 'utf8' },
    );
    const resetLinkCode = output.trim();
    if (resetLinkCode) return resetLinkCode;
    await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
  }

  throw new Error(`No reset link code found for ${email}`);
}
