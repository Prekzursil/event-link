import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let authState: {
  isAuthenticated: boolean;
  isOrganizer: boolean;
  isAdmin: boolean;
  isLoading: boolean;
} = {
  isAuthenticated: false,
  isOrganizer: false,
  isAdmin: false,
  isLoading: false,
};

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

beforeEach(() => {
  globalThis.localStorage.setItem('language_preference', 'en');
  authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };
});

afterEach(() => {
  cleanup();
  globalThis.history.pushState({}, '', '/');
});

describe('App routing guards', () => {
  it('shows loading UI for guarded route while auth is loading', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: true };
    globalThis.history.pushState({}, '', '/my-events');

    render(<App />);

    expect(await screen.findByText(/Loading|Se încarcă/i)).toBeInTheDocument();
  });

  it('redirects unauthenticated protected routes to /login', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/my-events');

    render(<App />);

    expect(await screen.findByText('LoginPage')).toBeInTheDocument();
  });

  it('redirects unauthenticated organizer routes to /login', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/organizer');

    render(<App />);

    expect(await screen.findByText('LoginPage')).toBeInTheDocument();
  });

  it('allows organizer-only routes for organizer users', async () => {
    authState = { isAuthenticated: true, isOrganizer: true, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/organizer/events/new');

    render(<App />);

    expect(await screen.findByText('EventFormPage')).toBeInTheDocument();
  });

  it('redirects authenticated non-organizers to /forbidden', async () => {
    authState = { isAuthenticated: true, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/organizer');

    render(<App />);

    expect(await screen.findByText('ForbiddenPage')).toBeInTheDocument();
  });

  it('redirects unauthenticated admin routes to /login', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/admin');

    render(<App />);

    expect(await screen.findByText('LoginPage')).toBeInTheDocument();
  });

  it('redirects non-admin users from /admin to /forbidden', async () => {
    authState = { isAuthenticated: true, isOrganizer: true, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/admin');

    render(<App />);

    expect(await screen.findByText('ForbiddenPage')).toBeInTheDocument();
  });

  it('allows admin route for admin users', async () => {
    authState = { isAuthenticated: true, isOrganizer: true, isAdmin: true, isLoading: false };
    globalThis.history.pushState({}, '', '/admin');

    render(<App />);

    expect(await screen.findByText('AdminDashboardPage')).toBeInTheDocument();
  });

  it('redirects authenticated users away from guest routes', async () => {
    authState = { isAuthenticated: true, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/login');

    render(<App />);

    expect(await screen.findByText('EventsPage')).toBeInTheDocument();
  });

  it('renders guest routes and public auth utility routes', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };

    globalThis.history.pushState({}, '', '/register');
    render(<App />);
    expect(await screen.findByText('RegisterPage')).toBeInTheDocument();

    cleanup();
    globalThis.history.pushState({}, '', '/forgot-password');
    render(<App />);
    expect(await screen.findByText('ForgotPasswordPage')).toBeInTheDocument();

    cleanup();
    globalThis.history.pushState({}, '', '/reset-password');
    render(<App />);
    expect(await screen.findByText('ResetPasswordPage')).toBeInTheDocument();
  });

  it('renders event detail and organizer public profile routes', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };

    globalThis.history.pushState({}, '', '/events/42');
    render(<App />);
    expect(await screen.findByText('EventDetailPage')).toBeInTheDocument();

    cleanup();
    globalThis.history.pushState({}, '', '/organizers/7');
    render(<App />);
    expect(await screen.findByText('OrganizerProfilePage')).toBeInTheDocument();
  });


  it('renders protected route content when authenticated', async () => {
    authState = { isAuthenticated: true, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/my-events');

    render(<App />);

    expect(await screen.findByText('MyEventsPage')).toBeInTheDocument();
  });

  it('shows loading UI on organizer route while auth is loading', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: true };
    globalThis.history.pushState({}, '', '/organizer');

    render(<App />);

    expect(await screen.findByText(/Loading|Se încarcă/i)).toBeInTheDocument();
  });

  it('shows loading UI on admin route while auth is loading', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: true };
    globalThis.history.pushState({}, '', '/admin');

    render(<App />);

    expect(await screen.findByText(/Loading|Se încarcă/i)).toBeInTheDocument();
  });

  it('shows loading UI on guest route while auth is loading', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: true };
    globalThis.history.pushState({}, '', '/login');

    render(<App />);

    expect(await screen.findByText(/Loading|Se încarcă/i)).toBeInTheDocument();
  });
  it('renders a 404 page for unknown routes', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isAdmin: false, isLoading: false };
    globalThis.history.pushState({}, '', '/does-not-exist');

    render(<App />);

    expect(await screen.findByText('NotFoundPage')).toBeInTheDocument();
  });
});
