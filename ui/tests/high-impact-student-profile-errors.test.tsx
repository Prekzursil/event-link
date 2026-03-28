import React from 'react';
import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  StudentProfilePage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';
import {
  makeNotificationPreferences,
  makePersonalizationSettings,
  makeStudentProfile,
  makeUpdatedStudentProfile,
} from './page-test-data';

const {
  authServiceMock,
  authState,
  eventServiceMock,
  toastSpy,
} = getHighImpactPageFixtures();

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

it('covers StudentProfilePage sparse fallbacks and academic edge branches', async () => {
  eventServiceMock.getStudentProfile.mockResolvedValueOnce(
    makeStudentProfile(11, {
      full_name: undefined,
      city: undefined,
      university: undefined,
      faculty: undefined,
      study_level: undefined,
      study_year: undefined,
      interest_tags: [],
    }),
  );
  eventServiceMock.getPersonalizationSettings.mockResolvedValueOnce(
    makePersonalizationSettings({
      hidden_tags: [],
      blocked_organizers: [
        { id: 1, org_name: '', full_name: 'Fallback Organizer', email: 'full@test.local' },
        { id: 2, org_name: '', full_name: '', email: 'email-only@test.local' },
      ],
    }),
  );
  eventServiceMock.getNotificationPreferences.mockResolvedValueOnce(
    makeNotificationPreferences(),
  );
  eventServiceMock.getUniversityCatalog.mockResolvedValueOnce([
    { name: 'UTCN', city: 'Cluj', faculties: ['Automatica'] },
    { name: 'No City University', city: '', faculties: ['Letters'] },
  ]);
  eventServiceMock.updateStudentProfile.mockResolvedValueOnce(
    makeUpdatedStudentProfile(11, {
      full_name: undefined,
      city: undefined,
      university: undefined,
      faculty: undefined,
      study_level: undefined,
      study_year: undefined,
      interest_tags: [],
    }),
  );
  eventServiceMock.deleteMyAccount.mockRejectedValueOnce(new Error('plain-delete-fail'));

  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

  expect(screen.getByLabelText(/Full name|Nume complet/i)).toHaveValue('');
  expect(screen.getByLabelText(/City|Oraș/i)).toHaveValue('');
  expect(screen.getByLabelText(/University|Universitate/i)).toHaveValue('');
  expect(screen.getByLabelText(/Faculty|Facultate/i)).toHaveValue('');
  expect(screen.getByText('Fallback Organizer')).toBeInTheDocument();
  expect(screen.getAllByText('email-only@test.local').length).toBeGreaterThan(0);

  const musicTagCard = requireElement(
    screen.getByLabelText(/Muzică/i).closest('label'),
    'music tag card',
  );
  fireEvent.keyDown(musicTagCard, { key: 'Escape' });
  const musicCheckbox = requireElement(document.getElementById('tag-1'), 'music checkbox');
  fireEvent.keyDown(musicCheckbox, { key: 'Escape' });
  fireEvent.keyDown(musicCheckbox, { key: ' ' });

  fireEvent.click(screen.getByRole('button', { name: /Save changes|Salvează/i }));
  await waitFor(() =>
    expect(eventServiceMock.updateStudentProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: undefined,
        study_level: undefined,
        study_year: undefined,
      }),
    ),
  );
  expect(screen.getByLabelText(/Full name|Nume complet/i)).toHaveValue('');

  fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
  const sparseDialog = await screen.findByRole('dialog');
  fireEvent.change(within(sparseDialog).getByLabelText(/Access code|Cod de acces/i), {
    target: { value: 'plain-delete-code' },
  });
  fireEvent.click(
    within(sparseDialog).getAllByRole('button', {
      name: /Delete account|Șterge contul/i,
    })[0],
  );
  await waitFor(() =>
    expect(toastSpy).toHaveBeenLastCalledWith(
      expect.objectContaining({ description: 'Could not delete account.' }),
    ),
  );

  cleanup();
  eventServiceMock.getStudentProfile.mockResolvedValueOnce(
    makeStudentProfile(11, {
      city: 'Bucharest',
      university: 'UTCN',
      faculty: 'Automatica',
      study_level: 'bachelor',
      study_year: 2,
    }),
  );
  eventServiceMock.getPersonalizationSettings.mockResolvedValueOnce(
    makePersonalizationSettings(),
  );
  eventServiceMock.getNotificationPreferences.mockResolvedValueOnce(
    makeNotificationPreferences(),
  );
  eventServiceMock.getUniversityCatalog.mockResolvedValueOnce([
    { name: 'UTCN', city: 'Cluj', faculties: ['Automatica'] },
    { name: 'No Faculty University', city: 'Iasi', faculties: [] },
  ]);

  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

  const cityField = await screen.findByLabelText(/City|Oraș/i);
  const universityField = await screen.findByLabelText(/University|Universitate/i);
  const facultyField = await screen.findByLabelText(/Faculty|Facultate/i);

  const reactPropsKey = Object.keys(universityField).find((key) => key.startsWith('__reactProps$'));
  expect(reactPropsKey).toBeDefined();
  const reactProps = (universityField as HTMLInputElement & Record<string, unknown>)[
    reactPropsKey as string
  ] as { onChange?: (event: { target: { value: string } }) => void };
  act(() => {
    reactProps.onChange?.({ target: { value: 'UTCN' } });
  });
  await waitFor(() => {
    expect(facultyField).toHaveValue('Automatica');
    expect(cityField).toHaveValue('Bucharest');
  });

  fireEvent.change(universityField, { target: { value: 'No Faculty University' } });
  expect(facultyField).toHaveValue('');
  expect(screen.getByText(/Faculty list is not available yet/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /Master/i }));
}, 20000);
