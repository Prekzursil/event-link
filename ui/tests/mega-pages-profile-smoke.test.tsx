import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  StudentProfilePage,
  getMegaPagesSmokeFixtures,
} from './mega-pages-smoke.shared';

const { eventServiceMock } = getMegaPagesSmokeFixtures();

describe('mega pages profile smoke', () => {
  it('covers student profile load and primary actions', async () => {
    renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
    await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());
    await waitFor(() => expect(eventServiceMock.getAllTags).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));
    await waitFor(() => expect(eventServiceMock.updateStudentProfile).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Export data/i }));
    await waitFor(() => expect(eventServiceMock.exportMyData).toHaveBeenCalled());
  });
});
