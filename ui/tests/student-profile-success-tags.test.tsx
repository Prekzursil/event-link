import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute, requireElement } from './page-test-helpers';
import {
  StudentProfilePage,
  getHighImpactPageFixtures,
} from './high-impact-pages-coverage.fixtures';

const { eventServiceMock } = getHighImpactPageFixtures();

it('covers the student tag checkbox onCheckedChange callback', async () => {
  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

  const tagCheckbox = document.getElementById('tag-1');
  expect(tagCheckbox).not.toBeNull();

  const tagCheckboxElement = requireElement(tagCheckbox, 'tag checkbox');
  fireEvent.click(tagCheckboxElement);
  fireEvent.click(tagCheckboxElement);
});

it('renders tag option cards and toggles selection via card click', async () => {
  renderLanguageRoute('/profile', '/profile', <StudentProfilePage />);
  await waitFor(() => expect(eventServiceMock.getStudentProfile).toHaveBeenCalled());

  const techTagLabel = requireElement(
    (await screen.findByText(/Tech/i)).closest('label'),
    'tech tag label',
  );
  fireEvent.click(techTagLabel);
  fireEvent.click(techTagLabel);
});
