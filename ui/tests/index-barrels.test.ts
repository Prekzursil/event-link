import { describe, expect, it } from 'vitest';

import { Navbar, Footer, Layout } from '@/components/layout';
import { AdminDashboardPage } from '@/pages/admin';
import { LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage } from '@/pages/auth';
import { EventsPage, EventDetailPage } from '@/pages/events';
import { OrganizerDashboardPage, EventFormPage, ParticipantsPage, OrganizerProfilePage } from '@/pages/organizer';
import { StudentProfilePage } from '@/pages/profile';

describe('barrel exports', () => {
  it('exports layout symbols', () => {
    expect(Navbar).toBeDefined();
    expect(Footer).toBeDefined();
    expect(Layout).toBeDefined();
  });

  it('exports admin pages', () => {
    expect(AdminDashboardPage).toBeDefined();
  });

  it('exports auth pages', () => {
    expect(LoginPage).toBeDefined();
    expect(RegisterPage).toBeDefined();
    expect(ForgotPasswordPage).toBeDefined();
    expect(ResetPasswordPage).toBeDefined();
  });

  it('exports events pages', () => {
    expect(EventsPage).toBeDefined();
    expect(EventDetailPage).toBeDefined();
  });

  it('exports organizer pages', () => {
    expect(OrganizerDashboardPage).toBeDefined();
    expect(EventFormPage).toBeDefined();
    expect(ParticipantsPage).toBeDefined();
    expect(OrganizerProfilePage).toBeDefined();
  });

  it('exports profile pages', () => {
    expect(StudentProfilePage).toBeDefined();
  });
});
