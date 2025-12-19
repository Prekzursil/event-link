import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let authState: { isAuthenticated: boolean; isOrganizer: boolean; isLoading: boolean } = {
  isAuthenticated: false,
  isOrganizer: false,
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

vi.mock('@/pages/organizer', () => ({
  OrganizerDashboardPage: () => <div>OrganizerDashboardPage</div>,
  EventFormPage: () => <div>EventFormPage</div>,
  ParticipantsPage: () => <div>ParticipantsPage</div>,
  OrganizerProfilePage: () => <div>OrganizerProfilePage</div>,
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
  window.localStorage.setItem('language_preference', 'ro');
});

afterEach(() => {
  cleanup();
  window.history.pushState({}, '', '/');
});

describe('App routing guards', () => {
  it('redirects unauthenticated protected routes to /login', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isLoading: false };
    window.history.pushState({}, '', '/my-events');

    render(<App />);

    expect(await screen.findByText('LoginPage')).toBeInTheDocument();
  });

  it('redirects unauthenticated organizer routes to /login', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isLoading: false };
    window.history.pushState({}, '', '/organizer');

    render(<App />);

    expect(await screen.findByText('LoginPage')).toBeInTheDocument();
  });

  it('redirects authenticated non-organizers to /forbidden', async () => {
    authState = { isAuthenticated: true, isOrganizer: false, isLoading: false };
    window.history.pushState({}, '', '/organizer');

    render(<App />);

    expect(await screen.findByText('Acces interzis')).toBeInTheDocument();
  });

  it('redirects authenticated users away from /login', async () => {
    authState = { isAuthenticated: true, isOrganizer: false, isLoading: false };
    window.history.pushState({}, '', '/login');

    render(<App />);

    expect(await screen.findByText('EventsPage')).toBeInTheDocument();
  });

  it('renders a 404 page for unknown routes', async () => {
    authState = { isAuthenticated: false, isOrganizer: false, isLoading: false };
    window.history.pushState({}, '', '/does-not-exist');

    render(<App />);

    expect(await screen.findByText('Pagina nu a fost găsită')).toBeInTheDocument();
  });
});
