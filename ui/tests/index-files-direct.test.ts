import { describe, expect, it } from 'vitest';

import * as layoutIndex from '../src/components/layout/index';
import * as adminIndex from '../src/pages/admin/index';
import * as authIndex from '../src/pages/auth/index';
import * as eventsIndex from '../src/pages/events/index';
import * as organizerIndex from '../src/pages/organizer/index';
import * as profileIndex from '../src/pages/profile/index';

describe('direct index imports', () => {
  it('loads and exposes layout index exports', () => {
    expect(layoutIndex.Layout).toBeDefined();
    expect(layoutIndex.Navbar).toBeDefined();
    expect(layoutIndex.Footer).toBeDefined();
  });

  it('loads and exposes page index exports', () => {
    expect(adminIndex.AdminDashboardPage).toBeDefined();
    expect(authIndex.LoginPage).toBeDefined();
    expect(authIndex.RegisterPage).toBeDefined();
    expect(authIndex.ForgotPasswordPage).toBeDefined();
    expect(authIndex.ResetPasswordPage).toBeDefined();
    expect(eventsIndex.EventsPage).toBeDefined();
    expect(eventsIndex.EventDetailPage).toBeDefined();
    expect(organizerIndex.OrganizerDashboardPage).toBeDefined();
    expect(organizerIndex.EventFormPage).toBeDefined();
    expect(organizerIndex.ParticipantsPage).toBeDefined();
    expect(organizerIndex.OrganizerProfilePage).toBeDefined();
    expect(profileIndex.StudentProfilePage).toBeDefined();
  });
});
