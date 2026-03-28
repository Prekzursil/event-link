import React from 'react';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  StudentProfilePage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';

const { authServiceMock, authState, eventServiceMock, toastSpy } = getHighImpactPageFixtures();

it('covers StudentProfilePage fallback and error branches', async () => {
  eventServiceMock.getPersonalizationSettings.mockRejectedValueOnce(
    new Error('personalization-fail'),
  );
  eventServiceMock.getNotificationPreferences.mockRejectedValueOnce(
    new Error('notifications-fail'),
  );
  eventServiceMock.getUniversityCatalog.mockRejectedValueOnce(new Error('catalog-fail'));
  eventServiceMock.updateStudentProfile.mockRejectedValueOnce(new Error('save-fail'));
  authServiceMock.updateThemePreference.mockRejectedValueOnce(new Error('theme-fail'));
  authServiceMock.updateLanguagePreference.mockRejectedValueOnce(new Error('language-fail'));
  eventServiceMock.updateNotificationPreferences.mockRejectedValueOnce(
    new Error('notification-save-fail'),
  );
  eventServiceMock.deleteMyAccount.mockRejectedValueOnce({
    response: { data: { detail: 'bad-access-code' } },
  });

  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

  const musicTagLabel = requireElement(
    screen.getByLabelText(/Muzică/i).closest('label'),
    'music tag label',
  );
  const musicTagCheckbox = requireElement(document.getElementById('tag-1'), 'music tag checkbox');
  fireEvent.click(musicTagLabel);
  fireEvent.keyDown(musicTagCheckbox, { key: 'Enter' });
  fireEvent.keyDown(musicTagCheckbox, { key: ' ' });

  fireEvent.change(screen.getByLabelText(/University/i), { target: { value: 'UTCN' } });
  fireEvent.change(screen.getByLabelText(/Faculty/i), { target: { value: 'AI' } });
  fireEvent.change(screen.getByLabelText(/City/i), { target: { value: 'Cluj-Napoca' } });

  fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.click(screen.getByText(/Light/i));
  fireEvent.click(screen.getByText(/^Romanian$/i));
  await waitFor(() => expect(authServiceMock.updateThemePreference).toHaveBeenCalled());
  await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalled());

  const digestLabel = screen.getByText(/Weekly digest/i);
  const digestRow = digestLabel.closest('div')?.parentElement?.parentElement;
  fireEvent.click(within(requireElement(digestRow, 'digest row')).getByRole('checkbox'));
  await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

  fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
  const dialog = await screen.findByRole('dialog');
  const deleteButtons = within(dialog).getAllByRole('button', {
    name: /Delete account|Șterge contul/i,
  });
  fireEvent.click(deleteButtons[0]);
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText(/Access code/i), {
    target: { value: 'wrong-access-code' },
  });
  fireEvent.click(deleteButtons[0]);
  await waitFor(() =>
    expect(eventServiceMock.deleteMyAccount).toHaveBeenCalledWith('wrong-access-code'),
  );
}, 20000);

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
