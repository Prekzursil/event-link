import React from 'react';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useI18n } from '@/contexts/LanguageContext';
import { renderLanguageRoute, setEnglishPreference } from './page-test-helpers';

vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);

import { AdminUsersTab } from '@/pages/admin/admin-dashboard/AdminUsersTab';

function Harness() {
  const { language, t } = useI18n();
  const controller = { handleUpdateUser: vi.fn(), isLoadingUsers: false, language, loadUsers: vi.fn(), roleLabels: { admin: t.adminDashboard.roles.admin, organizator: t.adminDashboard.roles.organizer, student: t.adminDashboard.roles.student }, setUsersActive: vi.fn(), setUsersRole: vi.fn(), setUsersSearch: vi.fn(), t, totalUserPages: 1, users: [{ id: 1, email: 'no-name@test.local', full_name: null, role: 'student', is_active: true, created_at: '2030-01-01T00:00:00Z', last_seen_at: null, registrations_count: 0, attended_count: 0, events_created_count: 0 }], usersActive: 'all', usersPage: 1, usersRole: 'all', usersSearch: '', usersTotal: 1 } as never;
  return <AdminUsersTab controller={controller} />;
}

describe('admin users coverage', () => {
  it('renders user rows without optional full-name content', () => {
    setEnglishPreference();
    renderLanguageRoute('/admin', '/admin', <Harness />);
    expect(screen.getByText('no-name@test.local')).toBeInTheDocument();
    expect(screen.queryByText('Test User')).not.toBeInTheDocument();
    expect(screen.getByText('-')).toBeInTheDocument();
  });
});
