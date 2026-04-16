import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';

const { authState, toastSpy, navigateSpy, authServiceMock } = vi.hoisted(() => ({
  authState: {
    login: vi.fn(),
    register: vi.fn(),
    isAuthenticated: false,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    refreshUser: vi.fn(),
    logout: vi.fn(),
    user: null,
  },
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  authServiceMock: {
    requestPasswordReset: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock('@/services/auth.service', () => ({
  default: authServiceMock,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';

/**
 * Renders the with providers scaffolding for tests.
 */
function renderWithProviders(node: React.ReactNode, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LanguageProvider>
        <Routes>
          <Route path="*" element={node} />
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

/**
 * Returns the form value or fails loudly when absent.
 */
function requireForm(buttonName: RegExp): HTMLFormElement {
  const form = screen.getByRole('button', { name: buttonName }).closest('form');
  if (!(form instanceof HTMLFormElement)) {
    throw new TypeError(`Expected a form for ${buttonName.toString()}`);
  }
  return form;
}

/**
 * Renders the register page scaffolding for tests.
 */
function renderRegisterPage() {
  cleanup();
  renderWithProviders(<RegisterPage />, '/register');
}

/**
 * Test helper: populate register form.
 */
function populateRegisterForm(
  password: string,
  confirmPassword: string,
  options: Readonly<{
    email?: string;
  }> = {},
) {
  const { email = 'x@test.ro' } = options;
  fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/^Access code$/i), { target: { value: password } });
  fireEvent.change(screen.getByLabelText(/Confirm access code/i), {
    target: { value: confirmPassword },
  });
}

describe('auth pages', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.setItem('language_preference', 'en');
    authState.login.mockResolvedValue();
    authState.register.mockResolvedValue();
    authServiceMock.requestPasswordReset.mockResolvedValue();
    authServiceMock.resetPassword.mockResolvedValue();
  });

  it('covers LoginPage success and failure paths', async () => {
    renderWithProviders(<LoginPage />, '/login');

    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'x@test.ro' } });
    fireEvent.change(screen.getByLabelText(/Access code/i), { target: { value: 'AccessCode123A' } });
    const loginToggle = document.querySelector<HTMLButtonElement>('button.absolute.right-0.top-0');
    expect(loginToggle).not.toBeNull();
    fireEvent.click(loginToggle);
    fireEvent.submit(requireForm(/Sign in/i));

    await waitFor(() => expect(authState.login).toHaveBeenCalledWith('x@test.ro', 'AccessCode123A'));
    expect(toastSpy).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalled();

    authState.login.mockRejectedValueOnce({ response: { data: { detail: 'bad creds' } } });
    fireEvent.submit(requireForm(/Sign in/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    authState.login.mockRejectedValueOnce({ response: { data: { error: { message: 'nested login error' } } } });
    fireEvent.submit(requireForm(/Sign in/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    authState.login.mockRejectedValueOnce(new Error('plain login failure'));
    fireEvent.submit(requireForm(/Sign in/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers RegisterPage mismatch, invalid password, success, and failure', async () => {
    renderRegisterPage();
    const registerToggle = document.querySelector<HTMLButtonElement>('button.absolute.right-0.top-0');
    expect(registerToggle).not.toBeNull();
    fireEvent.click(registerToggle);
    populateRegisterForm('AccessCode123A', 'OtherCode123A');
    fireEvent.submit(requireForm(/Create account/i));
    expect(toastSpy).toHaveBeenCalled();

    renderRegisterPage();
    populateRegisterForm('short', 'short');
    fireEvent.submit(requireForm(/Create account/i));
    expect(toastSpy).toHaveBeenCalled();

    renderRegisterPage();
    populateRegisterForm('AccessCode123A', 'AccessCode123A');
    fireEvent.submit(requireForm(/Create account/i));
    await waitFor(() => expect(authState.register).toHaveBeenCalled());
    expect(navigateSpy).toHaveBeenCalledWith('/');

    authState.register.mockRejectedValueOnce({ response: { data: { detail: 'register error' } } });
    renderRegisterPage();
    populateRegisterForm('AccessCode123A', 'AccessCode123A', {
      email: 'detail@test.ro',
    });
    fireEvent.submit(requireForm(/Create account/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    authState.register.mockRejectedValueOnce({ response: { data: { error: { message: 'nested register error' } } } });
    renderRegisterPage();
    populateRegisterForm('AccessCode123A', 'AccessCode123A', {
      email: 'nested@test.ro',
    });
    fireEvent.submit(requireForm(/Create account/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    authState.register.mockRejectedValueOnce(new Error('plain register failure'));
    renderRegisterPage();
    populateRegisterForm('AccessCode123A', 'AccessCode123A', {
      email: 'plain@test.ro',
    });
    fireEvent.submit(requireForm(/Create account/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });

  it('covers ForgotPasswordPage submit branches', async () => {
    renderWithProviders(<ForgotPasswordPage />, '/forgot-password');

    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'x@test.ro' } });
    fireEvent.submit(requireForm(/Send reset link/i));
    await waitFor(() => expect(authServiceMock.requestPasswordReset).toHaveBeenCalledWith('x@test.ro'));
    expect(screen.getByText(/Check your email/i)).toBeInTheDocument();

    authServiceMock.requestPasswordReset.mockRejectedValueOnce(new Error('ignored'));
    cleanup();
    renderWithProviders(<ForgotPasswordPage />, '/forgot-password');
    fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'y@test.ro' } });
    fireEvent.submit(requireForm(/Send reset link/i));
    await waitFor(() => expect(screen.getByText(/Check your email/i)).toBeInTheDocument());
  });

  it('covers ResetPasswordPage token-less and token-based branches', async () => {
    renderWithProviders(<ResetPasswordPage />, '/reset-password');
    expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument();

    cleanup();
    renderWithProviders(<ResetPasswordPage />, '/reset-password?token=abc');
    fireEvent.change(screen.getByLabelText(/New access code/i), { target: { value: 'AccessCode123A' } });
    fireEvent.change(screen.getByLabelText(/Confirm access code/i), { target: { value: 'MismatchCode123A' } });
    fireEvent.submit(requireForm(/Reset access code/i));
    expect(toastSpy).toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/New access code/i), { target: { value: 'short' } });
    fireEvent.change(screen.getByLabelText(/Confirm access code/i), { target: { value: 'short' } });
    fireEvent.submit(requireForm(/Reset access code/i));
    expect(toastSpy).toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/New access code/i), { target: { value: '12345678' } });
    fireEvent.change(screen.getByLabelText(/Confirm access code/i), { target: { value: '12345678' } });
    fireEvent.submit(requireForm(/Reset access code/i));
    expect(toastSpy).toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/New access code/i), { target: { value: 'OnlyLetters' } });
    fireEvent.change(screen.getByLabelText(/Confirm access code/i), { target: { value: 'OnlyLetters' } });
    fireEvent.submit(requireForm(/Reset access code/i));
    expect(toastSpy).toHaveBeenCalled();

    const toggleButton = document.querySelector<HTMLButtonElement>('button.absolute.right-0.top-0');
    expect(toggleButton).not.toBeNull();
    fireEvent.click(toggleButton);

    fireEvent.change(screen.getByLabelText(/New access code/i), { target: { value: 'AccessCode123A' } });
    fireEvent.change(screen.getByLabelText(/Confirm access code/i), { target: { value: 'AccessCode123A' } });
    fireEvent.submit(requireForm(/Reset access code/i));
    await waitFor(() => expect(authServiceMock.resetPassword).toHaveBeenCalledWith('abc', 'AccessCode123A', 'AccessCode123A'));
    expect(navigateSpy).toHaveBeenCalledWith('/login');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Reset access code/i })).not.toBeDisabled(),
    );

    authServiceMock.resetPassword.mockRejectedValueOnce({ response: { data: { detail: 'bad token' } } });
    fireEvent.submit(requireForm(/Reset access code/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Reset access code/i })).not.toBeDisabled(),
    );

    authServiceMock.resetPassword.mockRejectedValueOnce(new Error('reset-fallback'));
    fireEvent.submit(requireForm(/Reset access code/i));
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  });
});
