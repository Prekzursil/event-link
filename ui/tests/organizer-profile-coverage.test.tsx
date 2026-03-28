import React from 'react';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { renderLanguageRoute, setEnglishPreference } from './page-test-helpers';

const { eventServiceMock } = vi.hoisted(() => ({
  eventServiceMock: {
    getOrganizerProfile: vi.fn(),
  },
}));

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/components/events/EventCard', () => ({
  EventCard: ({
    event,
    isPast,
  }: {
    event: { id: number; title: string };
    isPast?: boolean;
  }) => <div data-testid={`organizer-event-${event.id}`}>{`${event.title}${isPast ? ' past' : ''}`}</div>,
}));

import { OrganizerProfilePage } from '@/pages/organizer/OrganizerProfilePage';

function makeEvent(id: number, startOffsetHours: number) {
  return {
    id,
    title: `Organizer Event ${id}`,
    description: `Description ${id}`,
    category: 'Technical',
    start_time: new Date(Date.now() + startOffsetHours * 3_600_000).toISOString(),
    end_time: new Date(Date.now() + (startOffsetHours + 1) * 3_600_000).toISOString(),
    city: 'Cluj',
    location: 'Main Hall',
    max_seats: 30,
    seats_taken: 3,
    tags: [],
    owner_id: 7,
    owner_name: 'Organizer',
    status: 'published',
  };
}

function makeOrganizerProfile(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    full_name: 'Organizer Name',
    org_name: 'Organizer Team',
    org_logo_url: '',
    org_description: 'Organizer profile',
    org_website: 'https://example.org',
    email: 'org@test.local',
    events: [makeEvent(1, 24), makeEvent(2, -24)],
    ...overrides,
  };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();
  eventServiceMock.getOrganizerProfile.mockResolvedValue(makeOrganizerProfile());
});

describe('organizer profile coverage', () => {
  it('covers missing-id and missing-profile not-found branches', async () => {
    renderLanguageRoute('/organizers', '/organizers', <OrganizerProfilePage />);
    expect(eventServiceMock.getOrganizerProfile).not.toHaveBeenCalled();
    expect(await screen.findByText(/Organizer not found/i)).toBeInTheDocument();
    expect(screen.getByText(/This organizer does not exist or is no longer available/i)).toBeInTheDocument();

    cleanup();
    eventServiceMock.getOrganizerProfile.mockResolvedValueOnce(null);
    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/This organizer does not exist or is no longer available/i)).toBeInTheDocument();
  });

  it('covers display-name fallbacks and empty-tab states', async () => {
    eventServiceMock.getOrganizerProfile.mockResolvedValueOnce(
      makeOrganizerProfile({
        org_name: '',
        full_name: 'Fallback Person',
        events: [],
      }),
    );

    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByText('Fallback Person')).toBeInTheDocument();
    expect(screen.getByText(/No upcoming events/i)).toBeInTheDocument();

    const pastTab = screen.getByRole('tab', { name: /Past/i });
    fireEvent.mouseDown(pastTab);
    fireEvent.click(pastTab);
    await waitFor(() => expect(pastTab).toHaveAttribute('data-state', 'active'));
    expect(screen.getByRole('heading', { name: /No past events/i })).toBeInTheDocument();

    const allTab = screen.getByRole('tab', { name: /All/i });
    fireEvent.mouseDown(allTab);
    fireEvent.click(allTab);
    await waitFor(() => expect(allTab).toHaveAttribute('data-state', 'active'));
    expect(screen.getByRole('heading', { name: /^No events$/i })).toBeInTheDocument();

    cleanup();
    eventServiceMock.getOrganizerProfile.mockResolvedValueOnce(
      makeOrganizerProfile({
        org_name: '',
        full_name: '',
        email: 'fallback@test.local',
        events: [makeEvent(5, 24)],
      }),
    );

    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByRole('heading', { name: /^Organizer$/i })).toBeInTheDocument();
    expect(screen.getByTestId('organizer-event-5')).toBeInTheDocument();

    cleanup();
    eventServiceMock.getOrganizerProfile.mockResolvedValueOnce(
      makeOrganizerProfile({
        org_website: '',
        email: '',
        events: [makeEvent(6, 24)],
      }),
    );

    renderLanguageRoute('/organizers/7', '/organizers/:id', <OrganizerProfilePage />);
    await waitFor(() => expect(eventServiceMock.getOrganizerProfile).toHaveBeenCalledWith(7));
    expect(await screen.findByTestId('organizer-event-6')).toBeInTheDocument();
    expect(screen.queryByText('org@test.local')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Website/i })).not.toBeInTheDocument();
  });
});
