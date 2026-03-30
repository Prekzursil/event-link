import { describe, expect, it } from 'vitest';

import { Layout, Navbar, Footer } from '../src/components/layout/index';
import { AdminDashboardPage } from '../src/pages/admin/index';
import { LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage } from '../src/pages/auth/index';
import { EventsPage, EventDetailPage } from '../src/pages/events/index';
import { OrganizerDashboardPage, EventFormPage, ParticipantsPage, OrganizerProfilePage } from '../src/pages/organizer/index';
import { StudentProfilePage } from '../src/pages/profile/index';

describe('direct index imports', () => {
  it('loads and exposes layout index exports', () => {
    expect(Layout).toBeDefined();
    expect(Navbar).toBeDefined();
    expect(Footer).toBeDefined();
  });

  it('loads and exposes page index exports', () => {
    expect(AdminDashboardPage).toBeDefined();
    expect(LoginPage).toBeDefined();
    expect(RegisterPage).toBeDefined();
    expect(ForgotPasswordPage).toBeDefined();
    expect(ResetPasswordPage).toBeDefined();
    expect(EventsPage).toBeDefined();
    expect(EventDetailPage).toBeDefined();
    expect(OrganizerDashboardPage).toBeDefined();
    expect(EventFormPage).toBeDefined();
    expect(ParticipantsPage).toBeDefined();
    expect(OrganizerProfilePage).toBeDefined();
    expect(StudentProfilePage).toBeDefined();
  });
});
