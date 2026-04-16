import { cleanup } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

import { defineMutableValue, setEnglishPreference } from './page-test-helpers';

const megaPageFixtures = vi.hoisted(() => ({
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
  eventServiceMock: {
    getEvent: vi.fn(),
    registerForEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    addToFavorites: vi.fn(),
    removeFromFavorites: vi.fn(),
    cloneEvent: vi.fn(),
    hideTag: vi.fn(),
    blockOrganizer: vi.fn(),
    getOrganizerEvents: vi.fn(),
    deleteEvent: vi.fn(),
    restoreEvent: vi.fn(),
    bulkUpdateEventStatus: vi.fn(),
    bulkUpdateEventTags: vi.fn(),
    getEventParticipants: vi.fn(),
    updateParticipantAttendance: vi.fn(),
    emailEventParticipants: vi.fn(),
    getStudentProfile: vi.fn(),
    getAllTags: vi.fn(),
    getPersonalizationSettings: vi.fn(),
    getNotificationPreferences: vi.fn(),
    getUniversityCatalog: vi.fn(),
    updateStudentProfile: vi.fn(),
    updateNotificationPreferences: vi.fn(),
    unhideTag: vi.fn(),
    unblockOrganizer: vi.fn(),
    exportMyData: vi.fn(),
    deleteMyAccount: vi.fn(),
  },
  adminServiceMock: {
    getStats: vi.fn(),
    getUsers: vi.fn(),
    updateUser: vi.fn(),
    getEvents: vi.fn(),
    reviewEventModeration: vi.fn(),
    getPersonalizationMetrics: vi.fn(),
    enqueueRecommendationsRetrain: vi.fn(),
    enqueueWeeklyDigest: vi.fn(),
    enqueueFillingFast: vi.fn(),
  },
  authServiceMock: {
    updateThemePreference: vi.fn(),
    updateLanguagePreference: vi.fn(),
  },
  authState: {
    isAuthenticated: true,
    isOrganizer: true,
    isAdmin: true,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  themeState: {
    preference: 'system',
    setPreference: vi.fn(),
  },
}));

const {
  toastSpy,
  navigateSpy,
  eventServiceMock,
  adminServiceMock,
  authServiceMock,
  authState,
  themeState,
} = megaPageFixtures;

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/admin.service', () => ({ default: adminServiceMock }));
vi.mock('@/services/auth.service', () => ({ default: authServiceMock }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));
vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => themeState }));
vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);
vi.mock('@/components/ui/dropdown-menu', () =>
  import('./mock-component-modules').then((module) => module.createDropdownMenuMockModule()),
);
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

/**
 * Test helper: get mega page fixtures.
 */
export function getMegaPageFixtures() {
  return megaPageFixtures;
}

const { AdminDashboardPage } = await import('@/pages/admin/AdminDashboardPage');
const { EventDetailPage } = await import('@/pages/events/EventDetailPage');
const { OrganizerDashboardPage } = await import('@/pages/organizer/OrganizerDashboardPage');
const { ParticipantsPage } = await import('@/pages/organizer/ParticipantsPage');
const { StudentProfilePage } = await import('@/pages/profile/StudentProfilePage');

export {
  AdminDashboardPage,
  EventDetailPage,
  OrganizerDashboardPage,
  ParticipantsPage,
  StudentProfilePage,
};

const {
  makeAdminEventPage,
  makeAdminStats,
  makeAdminUser,
  makeAdminUserPage,
  makeEventDetail,
  makeNotificationPreferences,
  makeOrganizerEvent,
  makeParticipantsPage,
  makePersonalizationMetrics,
  makePersonalizationSettings,
  makeStudentProfile,
  makeUniversityCatalog,
  makeUpdatedStudentProfile,
} = await import('./page-test-data');

export { makeEventDetail };

/**
 * Test helper: seed core auth and globals.
 */
function seedCoreAuthAndGlobals() {
  defineMutableValue(globalThis, 'confirm', vi.fn().mockReturnValue(true));
  defineMutableValue(globalThis, 'open', vi.fn());
  defineMutableValue(URL, 'createObjectURL', vi.fn().mockReturnValue('blob://csv'));
  authState.isAuthenticated = true;
  authState.isOrganizer = true;
  authState.isAdmin = true;
  authState.user = { id: 1, role: 'student', email: 'student@test.local' };
  authState.refreshUser.mockResolvedValue();
  authState.logout.mockResolvedValue();
}

/**
 * Test helper: seed event service defaults.
 */
function seedEventServiceDefaults() {
  eventServiceMock.getEvent.mockResolvedValue(makeEventDetail(1));
  eventServiceMock.registerForEvent.mockResolvedValue();
  eventServiceMock.unregisterFromEvent.mockResolvedValue();
  eventServiceMock.resendRegistrationEmail.mockResolvedValue();
  eventServiceMock.cloneEvent.mockResolvedValue({ id: 88 });
  eventServiceMock.addToFavorites.mockResolvedValue();
  eventServiceMock.removeFromFavorites.mockResolvedValue();
  eventServiceMock.hideTag.mockResolvedValue();
  eventServiceMock.blockOrganizer.mockResolvedValue();
  eventServiceMock.getOrganizerEvents.mockResolvedValue([makeOrganizerEvent(3)]);
  eventServiceMock.bulkUpdateEventStatus.mockResolvedValue({ updated: 1 });
  eventServiceMock.bulkUpdateEventTags.mockResolvedValue({ updated: 1 });
  eventServiceMock.deleteEvent.mockResolvedValue();
  eventServiceMock.restoreEvent.mockResolvedValue({ ok: true });
  eventServiceMock.getEventParticipants.mockResolvedValue(makeParticipantsPage(3));
  eventServiceMock.updateParticipantAttendance.mockResolvedValue();
  eventServiceMock.emailEventParticipants.mockResolvedValue({ recipients: 1 });
}

/**
 * Test helper: seed student profile defaults.
 */
function seedStudentProfileDefaults() {
  eventServiceMock.getStudentProfile.mockResolvedValue(makeStudentProfile(1));
  eventServiceMock.getAllTags.mockResolvedValue([
    { id: 1, name: 'Muzică' },
    { id: 2, name: 'Tech' },
  ]);
  eventServiceMock.getPersonalizationSettings.mockResolvedValue(makePersonalizationSettings());
  eventServiceMock.getNotificationPreferences.mockResolvedValue(makeNotificationPreferences());
  eventServiceMock.getUniversityCatalog.mockResolvedValue(makeUniversityCatalog());
  eventServiceMock.updateStudentProfile.mockResolvedValue(makeUpdatedStudentProfile(1));
  eventServiceMock.updateNotificationPreferences.mockResolvedValue(
    makeNotificationPreferences({
      email_digest_enabled: false,
      email_filling_fast_enabled: true,
    }),
  );
  eventServiceMock.unhideTag.mockResolvedValue();
  eventServiceMock.unblockOrganizer.mockResolvedValue();
  eventServiceMock.exportMyData.mockResolvedValue(
    new Blob(['{"ok":true}'], { type: 'application/json' }),
  );
  eventServiceMock.deleteMyAccount.mockResolvedValue();
}

/**
 * Test helper: seed admin stats and users defaults.
 */
function seedAdminStatsAndUsersDefaults() {
  adminServiceMock.getStats.mockResolvedValue(makeAdminStats());
  adminServiceMock.getUsers.mockResolvedValue(makeAdminUserPage());
  adminServiceMock.updateUser.mockResolvedValue(makeAdminUser(1, { role: 'admin' }));
}

/**
 * Test helper: seed admin event defaults.
 */
function seedAdminEventDefaults() {
  adminServiceMock.getEvents.mockResolvedValue(makeAdminEventPage());
  adminServiceMock.reviewEventModeration.mockResolvedValue({ ok: true });
}

/**
 * Test helper: seed admin job defaults.
 */
function seedAdminJobDefaults() {
  adminServiceMock.getPersonalizationMetrics.mockResolvedValue(makePersonalizationMetrics());
  adminServiceMock.enqueueRecommendationsRetrain.mockResolvedValue({
    job_id: 1,
    job_type: 'retrain',
    status: 'queued',
  });
  adminServiceMock.enqueueWeeklyDigest.mockResolvedValue({
    job_id: 2,
    job_type: 'digest',
    status: 'queued',
  });
  adminServiceMock.enqueueFillingFast.mockResolvedValue({
    job_id: 3,
    job_type: 'filling-fast',
    status: 'queued',
  });
}

/**
 * Test helper: seed auth service defaults.
 */
function seedAuthServiceDefaults() {
  authServiceMock.updateThemePreference.mockResolvedValue();
  authServiceMock.updateLanguagePreference.mockResolvedValue();
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();
  seedCoreAuthAndGlobals();
  seedEventServiceDefaults();
  seedStudentProfileDefaults();
  seedAdminStatsAndUsersDefaults();
  seedAdminEventDefaults();
  seedAdminJobDefaults();
  seedAuthServiceDefaults();
});
