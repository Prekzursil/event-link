import { describe, expect, it } from 'vitest';

import * as layout from '@/components/layout';
import * as adminPages from '@/pages/admin';
import * as authPages from '@/pages/auth';
import * as eventsPages from '@/pages/events';
import * as organizerPages from '@/pages/organizer';
import * as profilePages from '@/pages/profile';

describe('barrel exports', () => {
  it('exports layout symbols', () => {
    expect(layout.Navbar).toBeDefined();
    expect(layout.Footer).toBeDefined();
    expect(layout.Layout).toBeDefined();
  });

  it('exports admin pages', () => {
    expect(adminPages.AdminDashboardPage).toBeDefined();
  });

  it('exports auth pages', () => {
    expect(authPages.LoginPage).toBeDefined();
    expect(authPages.RegisterPage).toBeDefined();
    expect(authPages.ForgotPasswordPage).toBeDefined();
    expect(authPages.ResetPasswordPage).toBeDefined();
  });

  it('exports events pages', () => {
    expect(eventsPages.EventsPage).toBeDefined();
    expect(eventsPages.EventDetailPage).toBeDefined();
  });

  it('exports organizer pages', () => {
    expect(organizerPages.OrganizerDashboardPage).toBeDefined();
    expect(organizerPages.EventFormPage).toBeDefined();
    expect(organizerPages.ParticipantsPage).toBeDefined();
    expect(organizerPages.OrganizerProfilePage).toBeDefined();
  });

  it('exports profile pages', () => {
    expect(profilePages.StudentProfilePage).toBeDefined();
  });
});