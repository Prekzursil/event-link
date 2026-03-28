import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  StudentProfilePage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';

const { authState, eventServiceMock, toastSpy } = getHighImpactPageFixtures();

it('covers StudentProfilePage non-student and load-failure branches', async () => {
  authState.user = { id: 11, role: 'organizator', email: 'org@test.local' };
  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
  expect(screen.queryByText(/Personalization/i)).not.toBeInTheDocument();

  authState.user = { id: 11, role: 'student', email: 'student@test.local' };
  eventServiceMock.getStudentProfile.mockRejectedValueOnce(new Error('profile-load-fail'));
  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
});
