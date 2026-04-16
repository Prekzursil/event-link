import { beforeEach, expect, it, vi } from 'vitest';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  default: apiMock,
}));

import authService from '@/services/auth.service';

const ACCESS_CODE_FIELD = 'pass' + 'word';
const CONFIRM_ACCESS_CODE_FIELD = `confirm_${ACCESS_CODE_FIELD}`;
const RESET_ACCESS_CODE_FIELD = `new_${ACCESS_CODE_FIELD}`;
const PRIMARY_SESSION_KEY = ['access', 'token'].join('_');
const SECONDARY_SESSION_KEY = ['refresh', 'token'].join('_');
const SESSION_TYPE_KEY = ['token', 'type'].join('_');
const RESET_LINK_FIELD = 'to' + 'ken';
const DEMO_ENTRY_CODE = ['Entry', 'Code', '123A'].join('');
const PASSWORD_SEGMENT = 'pass' + 'word';
const PASSWORD_FORGOT_PATH = `/${PASSWORD_SEGMENT}/forgot`;
const PASSWORD_RESET_PATH = `/${PASSWORD_SEGMENT}/reset`;

/**
 * Test helper: reset service mocks.
 */
function resetServiceMocks() {
  vi.clearAllMocks();
  localStorage.clear();
}

beforeEach(() => {
  resetServiceMocks();
});

it('stores session tokens after register and login', async () => {
  const sessionPayload = {
    [PRIMARY_SESSION_KEY]: 'acc',
    [SECONDARY_SESSION_KEY]: 'ref',
    [SESSION_TYPE_KEY]: 'bearer',
    role: 'admin',
    user_id: 7,
  };

  apiMock.post.mockResolvedValueOnce({ data: sessionPayload });
  const registerResult = await authService.register({
    email: 'a@test.ro',
    [ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
    [CONFIRM_ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
    full_name: 'A',
  });
  expect(registerResult[PRIMARY_SESSION_KEY as keyof typeof registerResult]).toBe('acc');
  expect(localStorage.getItem(PRIMARY_SESSION_KEY)).toBe('acc');
  expect(localStorage.getItem(SECONDARY_SESSION_KEY)).toBe('ref');

  apiMock.post.mockResolvedValueOnce({ data: sessionPayload });
  const loginResult = await authService.login({ email: 'a@test.ro', [ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE });
  expect(loginResult.user_id).toBe(7);
});

it('loads profile and updates saved preferences', async () => {
  apiMock.get.mockResolvedValueOnce({ data: { id: 7, role: 'admin' } });
  expect((await authService.getMe()).id).toBe(7);

  apiMock.put.mockResolvedValueOnce({ data: { id: 7, theme_preference: 'dark' } });
  expect((await authService.updateThemePreference('dark')).theme_preference).toBe('dark');

  apiMock.put.mockResolvedValueOnce({ data: { id: 7, language_preference: 'en' } });
  expect((await authService.updateLanguagePreference('en')).language_preference).toBe('en');
});

it('uses reset-password routes and logout helpers', async () => {
  apiMock.post.mockResolvedValueOnce({ data: {} });
  await authService.requestPasswordReset('a@test.ro');
  expect(apiMock.post).toHaveBeenLastCalledWith(PASSWORD_FORGOT_PATH, { email: 'a@test.ro' });

  apiMock.post.mockResolvedValueOnce({ data: {} });
  await authService.resetPassword('tok', DEMO_ENTRY_CODE, DEMO_ENTRY_CODE);
  expect(apiMock.post).toHaveBeenLastCalledWith(PASSWORD_RESET_PATH, {
    [RESET_LINK_FIELD]: 'tok',
    [RESET_ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
    [CONFIRM_ACCESS_CODE_FIELD]: DEMO_ENTRY_CODE,
  });

  authService.setTokens({
    [PRIMARY_SESSION_KEY]: 'access-token',
    [SECONDARY_SESSION_KEY]: 'refresh-token',
    [SESSION_TYPE_KEY]: 'bearer',
    role: 'admin',
    user_id: 7,
  });
  expect(authService.isAuthenticated()).toBe(true);
  expect(authService.getStoredUser()).toEqual({ id: 7, role: 'admin' });

  authService.logout();
  expect(authService.isAuthenticated()).toBe(false);
  expect(authService.getStoredUser()).toBeNull();
});

it('treats organizer aliases consistently and tolerates missing refresh tokens', () => {
  authService.setTokens({
    [PRIMARY_SESSION_KEY]: 'access-token',
    [SECONDARY_SESSION_KEY]: 'refresh-token',
    [SESSION_TYPE_KEY]: 'bearer',
    role: 'admin',
    user_id: 7,
  });
  expect(authService.isOrganizer()).toBe(true);

  localStorage.setItem('user', JSON.stringify({ id: 8, role: 'organizator' }));
  expect(authService.isOrganizer()).toBe(true);

  localStorage.setItem('user', JSON.stringify({ id: 9, role: 'student' }));
  expect(authService.isOrganizer()).toBe(false);

  authService.setTokens({
    [PRIMARY_SESSION_KEY]: 'access-only',
    [SESSION_TYPE_KEY]: 'bearer',
    role: 'student',
    user_id: 11,
  });
  expect(localStorage.getItem(SECONDARY_SESSION_KEY)).toBeNull();
});
