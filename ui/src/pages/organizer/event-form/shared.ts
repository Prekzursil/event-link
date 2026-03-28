import type { Event, EventFormData, EventSuggestResponse } from '@/types';
import type { useI18n } from '@/contexts/LanguageContext';

type EventTag = { name: string };
type AxiosDetailError = { response?: { data?: { detail?: string } } };

export type EventFormTexts = ReturnType<typeof useI18n>['t'];
export type EventFormState = {
  title: string;
  description: string;
  category: string;
  start_time: string;
  end_time: string;
  city: string;
  location: string;
  max_seats: number | undefined;
  cover_url: string;
  tags: string[];
  status: 'draft' | 'published';
};

export const EMPTY_EVENT_FORM_STATE: EventFormState = {
  title: '',
  description: '',
  category: '',
  start_time: '',
  end_time: '',
  city: '',
  location: '',
  max_seats: undefined,
  cover_url: '',
  tags: [],
  status: 'published',
};

export function formatDateTimeLocal(dateString: string) {
  const date = new Date(dateString);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function errorDetail(error: unknown, fallback: string) {
  return (error as AxiosDetailError).response?.data?.detail || fallback;
}

function textOrEmpty(value: string | null | undefined) {
  return value ?? '';
}

function optionalDateTimeLocal(value: string | null | undefined) {
  return value ? formatDateTimeLocal(value) : '';
}

function eventStatus(value: Event['status'] | null | undefined): 'draft' | 'published' {
  return value === 'draft' ? 'draft' : 'published';
}

export function eventToFormState(event: Event & { tags: EventTag[] }): EventFormState {
  return {
    title: event.title,
    description: textOrEmpty(event.description),
    category: textOrEmpty(event.category),
    start_time: formatDateTimeLocal(event.start_time),
    end_time: optionalDateTimeLocal(event.end_time),
    city: textOrEmpty(event.city),
    location: textOrEmpty(event.location),
    max_seats: event.max_seats ?? undefined,
    cover_url: textOrEmpty(event.cover_url),
    tags: event.tags.map((tag) => tag.name),
    status: eventStatus(event.status),
  };
}

export function buildSuggestionPayload(formData: EventFormState) {
  return {
    title: formData.title.trim(),
    description: formData.description.trim() || undefined,
    category: formData.category || undefined,
    city: formData.city.trim() || undefined,
    location: formData.location.trim() || undefined,
    start_time: formData.start_time ? new Date(formData.start_time).toISOString() : undefined,
  };
}

export function applySuggestionToFormData(
  formData: EventFormState,
  suggestion: EventSuggestResponse,
): EventFormState {
  return {
    ...formData,
    category: formData.category || suggestion.suggested_category || '',
    city: formData.city || suggestion.suggested_city || '',
    tags: Array.from(new Set([...formData.tags, ...suggestion.suggested_tags].map((tag) => tag.trim()).filter(Boolean))),
  };
}

type EventFormValidator = Readonly<{
  invalid: (formData: EventFormState) => boolean;
  message: (t: EventFormTexts) => string;
}>;

function hasShortText(value: string) {
  return value.trim().length < 2;
}

const EVENT_FORM_VALIDATORS: readonly EventFormValidator[] = [
  {
    invalid: (formData) => !formData.title.trim(),
    message: (t) => t.eventForm.validation.titleRequired,
  },
  {
    invalid: (formData) => !formData.category,
    message: (t) => t.eventForm.validation.categoryRequired,
  },
  {
    invalid: (formData) => !formData.location || hasShortText(formData.location),
    message: (t) => t.eventForm.validation.locationRequired,
  },
  {
    invalid: (formData) => !formData.city || hasShortText(formData.city),
    message: (t) => t.eventForm.validation.cityRequired,
  },
  {
    invalid: (formData) => !formData.start_time,
    message: (t) => t.eventForm.validation.startRequired,
  },
  {
    invalid: (formData) => !formData.max_seats || formData.max_seats < 1,
    message: (t) => t.eventForm.validation.maxSeatsRequired,
  },
];

export function validateEventForm(formData: EventFormState, t: EventFormTexts) {
  const failingValidator = EVENT_FORM_VALIDATORS.find((validator) => validator.invalid(formData));
  return failingValidator ? failingValidator.message(t) : null;
}

export function buildEventPayload(formData: EventFormState): EventFormData {
  const trimmedDescription = formData.description.trim();
  const trimmedCoverUrl = formData.cover_url.trim();
  const payload: EventFormData = {
    title: formData.title.trim(),
    category: formData.category,
    city: formData.city.trim(),
    location: formData.location.trim(),
    start_time: new Date(formData.start_time).toISOString(),
    max_seats: formData.max_seats,
    status: formData.status,
    tags: formData.tags,
  };

  if (trimmedDescription) {
    payload.description = trimmedDescription;
  }
  if (formData.end_time) {
    payload.end_time = new Date(formData.end_time).toISOString();
  }
  if (trimmedCoverUrl) {
    payload.cover_url = trimmedCoverUrl;
  }
  return payload;
}

export function getSubmitLabel(isSaving: boolean, isEditing: boolean, t: EventFormTexts) {
  if (isSaving) {
    return t.eventForm.saving;
  }
  if (isEditing) {
    return t.eventForm.saveChanges;
  }
  return t.eventForm.createButton;
}
