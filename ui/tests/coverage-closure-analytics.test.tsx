import React from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { LanguageProvider } from '@/contexts/LanguageContext';
import { setEnglishPreference } from './page-test-helpers';

const {
  authState,
  eventServiceMock,
  recordInteractionsSpy,
  toastSpy,
  navigateSpy,
} = vi.hoisted(() => ({
  authState: {
    isAuthenticated: true,
    isOrganizer: false,
    isAdmin: false,
    isLoading: false,
    user: { id: 1, role: 'student', email: 'student@test.local' },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
  eventServiceMock: {
    addToFavorites: vi.fn(),
    blockOrganizer: vi.fn(),
    cloneEvent: vi.fn(),
    createEvent: vi.fn(),
    getEvent: vi.fn(),
    getEvents: vi.fn(),
    getFavorites: vi.fn(),
    hideTag: vi.fn(),
    registerForEvent: vi.fn(),
    removeFromFavorites: vi.fn(),
    resendRegistrationEmail: vi.fn(),
    suggestEvent: vi.fn(),
    unregisterFromEvent: vi.fn(),
    updateEvent: vi.fn(),
  },
  recordInteractionsSpy: vi.fn(),
  toastSpy: vi.fn(),
  navigateSpy: vi.fn(),
}));

vi.mock('@/services/event.service', () => ({ default: eventServiceMock }));
vi.mock('@/services/analytics.service', () => ({ recordInteractions: recordInteractionsSpy }));
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastSpy }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => authState }));
vi.mock('@/components/ui/select', () =>
  import('./mock-component-modules').then((module) => module.createSelectMockModule()),
);
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

import { EventsPage } from '@/pages/events/EventsPage';

type MatchMediaCallback = (event: { matches: boolean }) => void;

interface MatchMediaMock {
  media: string;
  matches: boolean;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  addListener: ReturnType<typeof vi.fn>;
  removeListener: ReturnType<typeof vi.fn>;
}

function createMatchMediaMock(): MatchMediaMock {
  return {
    media: '(min-width: 640px)',
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  };
}

function mountMatchMediaMock(mock: MatchMediaMock) {
  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn(() => mock),
  });
}

function renderEventsPage() {
  return render(
    <MemoryRouter initialEntries={['/events']}>
      <LanguageProvider>
        <Routes>
          <Route path="/events" element={<EventsPage />} />
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  setEnglishPreference();
  eventServiceMock.getEvents.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 12, total_pages: 1 });
  eventServiceMock.getFavorites.mockResolvedValue({ items: [] });
});

afterEach(() => {
  cleanup();
});

describe('analytics-side catch branches', () => {
  it('runs the EventsPage media-query change handler when the viewport toggles', async () => {
    const mediaMock = createMatchMediaMock();
    mountMatchMediaMock(mediaMock);
    recordInteractionsSpy.mockResolvedValue(undefined);

    renderEventsPage();

    await waitFor(() => expect(mediaMock.addEventListener).toHaveBeenCalled());
    const [, handler] = mediaMock.addEventListener.mock.calls[0] as [string, MatchMediaCallback];
    act(() => {
      handler({ matches: false });
    });
    act(() => {
      handler({ matches: true });
    });
    // The handler mutates layout state; no observable assertion is needed beyond no-throw.
    expect(mediaMock.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('swallows analytics rejections inside EventsPage impression tracking', async () => {
    mountMatchMediaMock(createMatchMediaMock());
    recordInteractionsSpy.mockRejectedValue(new Error('analytics down'));
    eventServiceMock.getEvents.mockResolvedValue({
      items: [
        {
          id: 1,
          title: 'Event One',
          description: 'desc',
          category: 'Technical',
          start_time: new Date(Date.now() + 3_600_000).toISOString(),
          end_time: new Date(Date.now() + 7_200_000).toISOString(),
          city: 'Cluj',
          location: 'Main Hall',
          max_seats: 20,
          seats_taken: 0,
          tags: [],
          owner_id: 1,
          owner_name: 'Owner',
          status: 'published',
        },
      ],
      total: 1,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });

    renderEventsPage();

    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());
    // Let the rejected catch chain resolve without throwing.
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Event One')).toBeInTheDocument();
  });
});

describe('useEventDetailController swallowPromise analytics path', () => {
  it('swallows analytics rejections when the detail page records interactions', async () => {
    mountMatchMediaMock(createMatchMediaMock());
    recordInteractionsSpy.mockRejectedValue(new Error('analytics down'));

    eventServiceMock.getEvent.mockResolvedValue({
      id: 9,
      title: 'Detail Fixture',
      description: 'desc',
      category: 'Technical',
      start_time: new Date(Date.now() + 3_600_000).toISOString(),
      end_time: new Date(Date.now() + 7_200_000).toISOString(),
      city: 'Cluj',
      location: 'Main Hall',
      max_seats: 20,
      seats_taken: 2,
      available_seats: 18,
      tags: [{ id: 1, name: 'Tech' }],
      owner_id: 9,
      owner_name: 'Organizer',
      is_owner: false,
      is_registered: false,
      is_favorite: false,
      status: 'published',
      cover_url: '',
    });

    const { useEventDetailController } = await import(
      '@/pages/events/event-detail/useEventDetailController'
    );

    function ProbeComponent() {
      const controller = useEventDetailController();
      return <div data-testid="detail-probe">{controller.event?.title ?? ''}</div>;
    }

    render(
      <MemoryRouter initialEntries={['/events/9']}>
        <LanguageProvider>
          <Routes>
            <Route path="/events/:id" element={<ProbeComponent />} />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(recordInteractionsSpy).toHaveBeenCalled());
    // Allow the rejected promise to settle through swallowPromise's catch handler.
    await act(async () => {
      await Promise.resolve();
    });
    expect(await screen.findByTestId('detail-probe')).toHaveTextContent('Detail Fixture');
  });
});
