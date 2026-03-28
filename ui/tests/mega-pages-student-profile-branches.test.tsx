import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  StudentProfilePage,
  getMegaPageFixtures,
} from './mega-pages-branches.fixtures';

const { authState, eventServiceMock, navigateSpy, toastSpy } = getMegaPageFixtures();

describe('mega pages student profile branches', () => {
  it('covers student profile save, export, delete, and personalization branches', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Export data/i }));
    await waitFor(() => expect(eventServiceMock.exportMyData).toHaveBeenCalled());

    const unblock = screen.getByRole('button', { name: /Unblock/i });
    fireEvent.click(unblock);
    await waitFor(() => expect(eventServiceMock.unblockOrganizer).toHaveBeenCalledWith(99));

    fireEvent.click(screen.getByRole('button', { name: /Delete account/i }));
    const dialog = await screen.findByRole('dialog');
    const destructiveButtons = within(dialog).getAllByRole('button', { name: /Delete account/i });
    fireEvent.click(destructiveButtons[0]);
    await waitFor(() => expect(toastSpy).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/Access code/i), {
      target: { value: 'secret-access-code' },
    });
    fireEvent.click(destructiveButtons[0]);
    await waitFor(() =>
      expect(eventServiceMock.deleteMyAccount).toHaveBeenCalledWith('secret-access-code'),
    );
    expect(authState.logout).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith('/');
  });
});
