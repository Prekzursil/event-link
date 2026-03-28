import { fireEvent, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import { renderLanguageRoute } from './page-test-helpers';
import {
  EventFormPage,
  getEventPagesFixtures,
} from './events-form-and-events-page.shared';

const { navigateSpy } = getEventPagesFixtures();

it('covers back and cancel navigation actions', () => {
  renderLanguageRoute('/organizer/events/new', '/organizer/events/new', <EventFormPage />);

  fireEvent.click(screen.getByRole('button', { name: /Back/i }));
  expect(navigateSpy).toHaveBeenCalledWith(-1);

  fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
  expect(navigateSpy).toHaveBeenCalledWith('/organizer');
});
