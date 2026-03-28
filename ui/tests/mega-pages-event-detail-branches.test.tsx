import React from 'react';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventDetailPage,
  getMegaPageFixtures,
  makeEventDetail,
} from './mega-pages-branches.fixtures';

const { authState, eventServiceMock, navigateSpy } = getMegaPageFixtures();

describe('mega pages event detail branches', () => {
  it('covers unauthenticated redirect and registered flows', async () => {
    authState.isAuthenticated = false;
    authState.user = null;
    renderLanguageRoute('/events/1', '/events/:id', <EventDetailPage />);

    await waitFor(() => expect(eventServiceMock.getEvent).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: /Register for event/i }));
    await waitFor(() =>
      expect(navigateSpy).toHaveBeenCalledWith('/login', {
        state: { from: { pathname: '/events/1' } },
      }),
    );

    cleanup();
    authState.isAuthenticated = true;
    authState.user = { id: 1, role: 'student', email: 'student@test.local' };
    eventServiceMock.getEvent.mockResolvedValueOnce({
      ...makeEventDetail(1),
      is_registered: true,
      is_favorite: true,
    });
    renderLanguageRoute('/events/1', '/events/:id', <EventDetailPage />);

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /Resend confirmation email/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('button', { name: /Resend confirmation email/i }));
    await waitFor(() => expect(eventServiceMock.resendRegistrationEmail).toHaveBeenCalledWith(1));

    fireEvent.click(screen.getByRole('button', { name: /Unregister/i }));
    await waitFor(() => expect(eventServiceMock.unregisterFromEvent).toHaveBeenCalledWith(1));
  });
});
