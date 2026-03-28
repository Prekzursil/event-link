import React from 'react';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement, requireInput } from './page-test-helpers';
import {
  StudentProfilePage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';

const { authServiceMock, eventServiceMock, toastSpy } = getHighImpactPageFixtures();

it('covers StudentProfilePage success handlers and guarded branches', async () => {
  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
  await screen.findByLabelText(/Full name/i);

  fireEvent.change(screen.getByLabelText(/Full name/i), { target: { value: 'New Name' } });

  const cityField = screen.getByLabelText(/City|Oraș/i);
  fireEvent.change(cityField, { target: { value: '' } });
  fireEvent.change(screen.getByLabelText(/University|Universitate/i), {
    target: { value: 'Other U' },
  });
  fireEvent.change(screen.getByLabelText(/University|Universitate/i), {
    target: { value: 'UTCN' },
  });

  const interestToggle = document.getElementById('tag-2');
  const interestToggleElement = requireElement(interestToggle, 'interest toggle');
  fireEvent.click(interestToggleElement);
  fireEvent.keyDown(interestToggleElement, { key: 'Enter' });

  const interestCheckbox = screen.getByRole('checkbox', { name: /Tech/i });
  fireEvent.click(interestCheckbox);

  const musicCheckbox = document.getElementById('tag-1');
  fireEvent.click(requireElement(musicCheckbox, 'music checkbox'));

  fireEvent.click(screen.getByRole('button', { name: /Master/i }));
  fireEvent.click(screen.getByRole('button', { name: /^1$/i }));

  fireEvent.click(screen.getByRole('button', { name: /Light/i }));
  fireEvent.click(screen.getByRole('button', { name: /^Romanian$/i }));
  await waitFor(() => expect(authServiceMock.updateThemePreference).toHaveBeenCalledWith('light'));
  await waitFor(() => expect(authServiceMock.updateLanguagePreference).toHaveBeenCalledWith('ro'));

  eventServiceMock.unhideTag.mockRejectedValueOnce(new Error('unhide-fail'));
  const firstHiddenButton = screen
    .getAllByRole('button')
    .find((button) => (button.textContent || '').trim() === '✕');
  fireEvent.click(requireElement(firstHiddenButton, 'first hidden tag button'));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  eventServiceMock.unhideTag.mockResolvedValueOnce(undefined);
  const secondHiddenButton = screen
    .getAllByRole('button')
    .find((button) => (button.textContent || '').trim() === '✕');
  fireEvent.click(requireElement(secondHiddenButton, 'second hidden tag button'));
  await waitFor(() => expect(eventServiceMock.unhideTag).toHaveBeenCalledWith(5));

  eventServiceMock.unblockOrganizer.mockRejectedValueOnce(new Error('unblock-fail'));
  fireEvent.click(screen.getByRole('button', { name: /Unblock|Deblochează/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  const digestLabel = screen.getByText(/Digest|Rezumat/i);
  const digestRow = digestLabel.closest('div')?.parentElement?.parentElement;
  fireEvent.click(within(requireElement(digestRow, 'digest row')).getByRole('checkbox'));
  await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

  const notificationsHeading = screen.getByText(/Notifications|Notificări/i);
  const notificationsCard = notificationsHeading.closest('div')?.parentElement?.parentElement;
  const notificationCheckboxes = within(
    requireElement(notificationsCard, 'notifications card'),
  ).getAllByRole('checkbox');
  fireEvent.click(notificationCheckboxes[notificationCheckboxes.length - 1]);
  await waitFor(() => expect(eventServiceMock.updateNotificationPreferences).toHaveBeenCalled());

  eventServiceMock.exportMyData.mockRejectedValueOnce(new Error('export-fail'));
  fireEvent.click(screen.getByRole('button', { name: /Export data|Export date/i }));
  await waitFor(() => expect(toastSpy).toHaveBeenCalled());

  fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
  const dialog = await screen.findByRole('dialog');
  const accessCodeField = requireInput(
    within(dialog).getByLabelText(/Access code|Cod de acces/i),
    'access code field',
  );
  fireEvent.change(accessCodeField, { target: { value: 'temporary-access-code' } });
  fireEvent.click(within(dialog).getByRole('button', { name: /Cancel|Anulează/i }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

  fireEvent.click(screen.getByRole('button', { name: /Delete account|Șterge contul/i }));
  const reopenedDialog = await screen.findByRole('dialog');
  const reopenedAccessCode = requireInput(
    within(reopenedDialog).getByLabelText(/Access code|Cod de acces/i),
    'reopened access code field',
  );
  expect(reopenedAccessCode).toHaveValue('');
  fireEvent.click(within(reopenedDialog).getByRole('button', { name: /Cancel|Anulează/i }));
}, 20000);
