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

const { eventServiceMock, toastSpy } = getHighImpactPageFixtures();

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
