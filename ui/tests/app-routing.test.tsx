import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type AuthState = {
  isAuthenticated: boolean;
  isOrganizer: boolean;
  isAdmin: boolean;
  isLoading: boolean;
};

type RouteCase = {
  path: string;
  expected: string | RegExp;
  state?: Partial<AuthState>;
};

const DEFAULT_AUTH_STATE: AuthState = {
  isAuthenticated: false,
  isOrganizer: false,
  isAdmin: false,
  isLoading: false,
};

const LOADING_TEXT = /Loading|Se încarcă/i;

let authState: AuthState = { ...DEFAULT_AUTH_STATE };

vi.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => authState,
}));

vi.mock('@/components/layout/Layout', async () => {
  const { Outlet } = await import('react-router-dom');
  return {
    Layout: () => <Outlet />,
  };
});

vi.mock('@/components/ui/toaster', () => ({
  Toaster: () => null,
}));

vi.mock('@/pages/events', () => ({
  EventsPage: () => <div>EventsPage</div>,
  EventDetailPage: () => <div>EventDetailPage</div>,
}));

vi.mock('@/pages/MyEventsPage', () => ({
  MyEventsPage: () => <div>MyEventsPage</div>,
}));

vi.mock('@/pages/FavoritesPage', () => ({
  FavoritesPage: () => <div>FavoritesPage</div>,
}));

vi.mock('@/pages/profile', () => ({
  StudentProfilePage: () => <div>StudentProfilePage</div>,
}));

vi.mock('@/pages/ForbiddenPage', () => ({
  ForbiddenPage: () => <div>ForbiddenPage</div>,
}));

vi.mock('@/pages/NotFoundPage', () => ({
  NotFoundPage: () => <div>NotFoundPage</div>,
}));

vi.mock('@/pages/organizer', () => ({
  OrganizerDashboardPage: () => <div>OrganizerDashboardPage</div>,
  EventFormPage: () => <div>EventFormPage</div>,
  ParticipantsPage: () => <div>ParticipantsPage</div>,
  OrganizerProfilePage: () => <div>OrganizerProfilePage</div>,
}));

vi.mock('@/pages/admin', () => ({
  AdminDashboardPage: () => <div>AdminDashboardPage</div>,
}));

vi.mock('@/pages/auth/LoginPage', () => ({
  LoginPage: () => <div>LoginPage</div>,
}));

vi.mock('@/pages/auth/RegisterPage', () => ({
  RegisterPage: () => <div>RegisterPage</div>,
}));

vi.mock('@/pages/auth/ForgotPasswordPage', () => ({
  ForgotPasswordPage: () => <div>ForgotPasswordPage</div>,
}));

vi.mock('@/pages/auth/ResetPasswordPage', () => ({
  ResetPasswordPage: () => <div>ResetPasswordPage</div>,
}));

import App from '@/App';

const renderRoute = (path: string, state: Partial<AuthState> = {}) => {
  authState = { ...DEFAULT_AUTH_STATE, ...state };
  globalThis.history.pushState({}, '', path);
  render(<App />);
};

beforeEach(() => {
  globalThis.localStorage.setItem('language_preference', 'en');
  authState = { ...DEFAULT_AUTH_STATE };
});

afterEach(() => {
  cleanup();
  globalThis.history.pushState({}, '', '/');
});

describe('App routing guards', () => {
  it.each(['/my-events', '/organizer', '/admin'])(
    'redirects unauthenticated users from %s to LoginPage',
    async (path) => {
      renderRoute(path);
      expect(await screen.findByText('LoginPage')).toBeInTheDocument();
    },
  );

  it.each(['/my-events', '/organizer', '/admin', '/login'])(
    'shows loading UI for %s while auth is loading',
    async (path) => {
      renderRoute(path, { isLoading: true });
      expect(await screen.findByText(LOADING_TEXT)).toBeInTheDocument();
    },
  );

  it.each<RouteCase>([
    { path: '/organizer/events/new', expected: 'EventFormPage', state: { isAuthenticated: true, isOrganizer: true } },
    { path: '/admin', expected: 'AdminDashboardPage', state: { isAuthenticated: true, isOrganizer: true, isAdmin: true } },
    { path: '/my-events', expected: 'MyEventsPage', state: { isAuthenticated: true } },
    { path: '/login', expected: 'EventsPage', state: { isAuthenticated: true } },
    { path: '/register', expected: 'RegisterPage' },
    { path: '/forgot-password', expected: 'ForgotPasswordPage' },
    { path: '/reset-password', expected: 'ResetPasswordPage' },
    { path: '/events/42', expected: 'EventDetailPage' },
    { path: '/organizers/7', expected: 'OrganizerProfilePage' },
    { path: '/does-not-exist', expected: 'NotFoundPage' },
  ])('renders $expected for $path', async ({ path, expected, state }) => {
    renderRoute(path, state);
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it.each<RouteCase>([
    { path: '/organizer', expected: 'ForbiddenPage', state: { isAuthenticated: true } },
    { path: '/admin', expected: 'ForbiddenPage', state: { isAuthenticated: true, isOrganizer: true } },
  ])('renders ForbiddenPage for blocked authenticated route $path', async ({ path, expected, state }) => {
    renderRoute(path, state);
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });
});
