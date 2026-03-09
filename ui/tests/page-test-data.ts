function hoursFromNow(hours: number) {
  return new Date(Date.now() + hours * 3_600_000).toISOString();
}

export function makeEvent(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    title: `Event ${id}`,
    description: `Description ${id}`,
    category: 'Technical',
    start_time: hoursFromNow(1),
    end_time: hoursFromNow(2),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 40,
    seats_taken: 4,
    tags: [{ id: 1, name: 'Tech' }],
    owner_id: 55,
    owner_name: 'Organizer',
    recommendation_reason: 'Recommended',
    status: 'published',
    ...overrides,
  };
}

export function makeEventDetail(id: number, overrides: Record<string, unknown> = {}) {
  return makeEvent(id, {
    location: 'Main hall',
    seats_taken: 12,
    tags: [{ id: 5, name: 'Tech' }],
    owner_id: 77,
    owner_name: 'Org Name',
    recommendation_reason: 'Great match',
    is_owner: false,
    is_registered: false,
    available_seats: 28,
    is_favorite: false,
    cover_url: '',
    ...overrides,
  });
}

export function makeStudentProfile(userId: number, overrides: Record<string, unknown> = {}) {
  return {
    user_id: userId,
    email: 'student@test.local',
    full_name: 'Student Name',
    city: 'Cluj',
    university: 'UTCN',
    faculty: 'Automatica',
    study_level: 'bachelor',
    study_year: 2,
    interest_tags: [{ id: 1, name: 'Muzică' }],
    ...overrides,
  };
}

export function makeUpdatedStudentProfile(userId: number, overrides: Record<string, unknown> = {}) {
  return makeStudentProfile(userId, {
    full_name: 'Student Name Updated',
    interest_tags: [{ id: 2, name: 'Tech' }],
    ...overrides,
  });
}

export function makePersonalizationSettings(overrides: Record<string, unknown> = {}) {
  return {
    hidden_tags: [{ id: 4, name: 'Hidden' }],
    blocked_organizers: [{ id: 99, org_name: 'Muted Org', email: 'muted@test.local' }],
    ...overrides,
  };
}

export function makeNotificationPreferences(overrides: Record<string, unknown> = {}) {
  return {
    email_digest_enabled: true,
    email_filling_fast_enabled: false,
    ...overrides,
  };
}

export function makeUniversityCatalog() {
  return [{ name: 'UTCN', city: 'Cluj', faculties: ['Automatica', 'Informatica'] }];
}

export function makeOrganizerEvent(id: number, overrides: Record<string, unknown> = {}) {
  return makeEvent(id, {
    description: 'desc',
    location: 'Room 1',
    max_seats: 30,
    seats_taken: 3,
    tags: [],
    owner_id: 1,
    ...overrides,
  });
}

export function makeParticipant(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    email: 'participant@test.local',
    full_name: 'Participant',
    registration_time: new Date().toISOString(),
    attended: false,
    ...overrides,
  };
}

export function makeParticipantsPage(eventId: number, overrides: Record<string, unknown> = {}) {
  return {
    event_id: eventId,
    title: 'Organizer event',
    seats_taken: 3,
    max_seats: 30,
    participants: [makeParticipant(10)],
    total: 40,
    page: 1,
    page_size: 20,
    ...overrides,
  };
}

export function makeAdminUser(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    email: 'student@test.local',
    full_name: 'Student Name',
    role: 'student',
    is_active: true,
    created_at: new Date().toISOString(),
    last_seen_at: new Date().toISOString(),
    registrations_count: 2,
    attended_count: 1,
    events_created_count: 0,
    ...overrides,
  };
}

export function makeAdminUserPage(overrides: Record<string, unknown> = {}) {
  return {
    items: [makeAdminUser(1)],
    total: 24,
    page: 1,
    page_size: 20,
    ...overrides,
  };
}

export function makeAdminEvent(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    title: id === 21 ? 'Admin flagged' : 'Admin deleted',
    description: id === 21 ? 'flagged' : 'deleted',
    category: 'Technical',
    start_time: new Date().toISOString(),
    end_time: hoursFromNow(1),
    status: id === 21 ? 'published' : 'draft',
    owner_id: id === 21 ? 7 : 8,
    owner_email: id === 21 ? 'org@test.local' : 'org2@test.local',
    owner_name: id === 21 ? 'Organizer' : 'Organizer2',
    seats_taken: id === 21 ? 1 : 0,
    max_seats: id === 21 ? 50 : 30,
    city: id === 21 ? 'Cluj' : 'Iasi',
    location: id === 21 ? 'Hall' : 'Room 10',
    tags: [],
    moderation_status: id === 21 ? 'flagged' : 'clean',
    moderation_score: id === 21 ? 0.91 : null,
    moderation_flags: id === 21 ? ['spam'] : [],
    deleted_at: id === 21 ? null : new Date().toISOString(),
    ...overrides,
  };
}

export function makeAdminEventPage(overrides: Record<string, unknown> = {}) {
  return {
    items: [makeAdminEvent(21), makeAdminEvent(22)],
    total: 24,
    page: 1,
    page_size: 20,
    ...overrides,
  };
}

export function makeAdminStats() {
  return {
    total_users: 3,
    total_events: 2,
    total_registrations: 6,
    registrations_by_day: [{ date: '2026-03-01', registrations: 2 }],
    top_tags: [{ name: 'Tech', registrations: 4, events: 2 }],
  };
}

export function makePersonalizationMetrics() {
  return {
    items: [
      {
        date: '2026-03-01',
        impressions: 40,
        clicks: 10,
        registrations: 3,
        ctr: 0.25,
        registration_conversion: 0.3,
      },
    ],
    totals: {
      impressions: 40,
      clicks: 10,
      registrations: 3,
      ctr: 0.25,
      registration_conversion: 0.3,
    },
  };
}
