import api from './api';
import type { 
  Event, 
  EventDetail, 
  PaginatedEvents, 
  EventFilters, 
  EventFormData,
  EventSuggestRequest,
  EventSuggestResponse,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  ParticipantList,
  OrganizerProfile,
  PersonalizationSettings,
  Tag,
  StudentProfile,
  StudentProfileUpdate,
  UniversityCatalogItem,
} from '../types';

/**
 * Test helper: append param.
 */
function appendParam(params: URLSearchParams, key: string, value: string | number | undefined | null) {
  if (value === undefined || value === null || value === '') {
    return;
  }
  params.append(key, String(value));
}


/**
 * Test helper: build event filters params.
 */
function buildEventFiltersParams(filters: EventFilters): URLSearchParams {
  const params = new URLSearchParams();
  appendParam(params, 'search', filters.search);
  appendParam(params, 'category', filters.category);
  appendParam(params, 'start_date', filters.start_date);
  appendParam(params, 'end_date', filters.end_date);
  appendParam(params, 'city', filters.city);
  appendParam(params, 'location', filters.location);
  appendParam(params, 'sort', filters.sort);
  appendParam(params, 'page', filters.page);
  appendParam(params, 'page_size', filters.page_size);
  if (filters.include_past) {
    params.append('include_past', 'true');
  }
  if (filters.tags?.length) {
    params.append('tags_csv', filters.tags.join(','));
  }
  return params;
}


export const eventService = {
  // Public event endpoints
  async getEvents(filters: EventFilters = {}): Promise<PaginatedEvents> {
    const params = buildEventFiltersParams(filters);
    const response = await api.get<PaginatedEvents>(`/api/events?${params.toString()}`);
    return response.data;
  },

  async getEvent(id: number): Promise<EventDetail> {
    const response = await api.get<EventDetail>(`/api/events/${id}`);
    return response.data;
  },

  async getEventIcs(id: number): Promise<string> {
    const response = await api.get(`/api/events/${id}/ics`, { responseType: 'text' });
    return response.data as string;
  },

  // Registration endpoints
  async registerForEvent(eventId: number): Promise<void> {
    await api.post(`/api/events/${eventId}/register`);
  },

  async unregisterFromEvent(eventId: number): Promise<void> {
    await api.delete(`/api/events/${eventId}/register`);
  },

  async resendRegistrationEmail(eventId: number): Promise<void> {
    await api.post(`/api/events/${eventId}/register/resend`);
  },

  // Favorites endpoints
  async addToFavorites(eventId: number): Promise<void> {
    await api.post(`/api/events/${eventId}/favorite`);
  },

  async removeFromFavorites(eventId: number): Promise<void> {
    await api.delete(`/api/events/${eventId}/favorite`);
  },

  async getFavorites(): Promise<{ items: Event[] }> {
    const response = await api.get<{ items: Event[] }>('/api/me/favorites');
    return response.data;
  },

  // User events
  async getMyEvents(): Promise<Event[]> {
    const response = await api.get<Event[]>('/api/me/events');
    return response.data;
  },

  async getMyCalendar(): Promise<string> {
    const response = await api.get('/api/me/calendar', { responseType: 'text' });
    return response.data as string;
  },

  // Account privacy
  async exportMyData(): Promise<Blob> {
    const response = await api.get('/api/me/export', { responseType: 'blob' });
    return response.data as Blob;
  },

  async deleteMyAccount(password: string): Promise<void> {
    await api.delete('/api/me', { data: { password } });
  },

  // Recommendations
  async getRecommendations(): Promise<Event[]> {
    const response = await api.get<Event[]>('/api/recommendations');
    return response.data;
  },

  // Organizer endpoints
  async createEvent(data: EventFormData): Promise<Event> {
    const response = await api.post<Event>('/api/events', data);
    return response.data;
  },

  async updateEvent(id: number, data: Partial<EventFormData>): Promise<Event> {
    const response = await api.put<Event>(`/api/events/${id}`, data);
    return response.data;
  },

  async deleteEvent(id: number): Promise<void> {
    await api.delete(`/api/events/${id}`);
  },

  async restoreEvent(id: number): Promise<{ status: string; restored_registrations?: number }> {
    const response = await api.post(`/api/events/${id}/restore`);
    return response.data as { status: string; restored_registrations?: number };
  },

  async cloneEvent(id: number): Promise<Event> {
    const response = await api.post<Event>(`/api/events/${id}/clone`);
    return response.data;
  },

  async getOrganizerEvents(): Promise<Event[]> {
    const response = await api.get<Event[]>('/api/organizer/events');
    return response.data;
  },

  async getEventParticipants(
    eventId: number, 
    page = 1, 
    pageSize = 20,
    sortBy = 'registration_time',
    sortDir = 'asc'
  ): Promise<ParticipantList> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    const response = await api.get<ParticipantList>(
      `/api/organizer/events/${eventId}/participants?${params.toString()}`
    );
    return response.data;
  },

  async updateParticipantAttendance(
    eventId: number, 
    userId: number, 
    attended: boolean
  ): Promise<void> {
    await api.put(
      `/api/organizer/events/${eventId}/participants/${userId}?attended=${attended}`
    );
  },

  async bulkUpdateEventStatus(
    eventIds: number[],
    status: 'draft' | 'published'
  ): Promise<{ updated: number }> {
    const response = await api.post<{ updated: number }>('/api/organizer/events/bulk/status', {
      event_ids: eventIds,
      status,
    });
    return response.data;
  },

  async bulkUpdateEventTags(eventIds: number[], tags: string[]): Promise<{ updated: number }> {
    const response = await api.post<{ updated: number }>('/api/organizer/events/bulk/tags', {
      event_ids: eventIds,
      tags,
    });
    return response.data;
  },

  async emailEventParticipants(
    eventId: number,
    subject: string,
    message: string
  ): Promise<{ recipients: number }> {
    const response = await api.post<{ recipients: number }>(
      `/api/organizer/events/${eventId}/participants/email`,
      { subject, message }
    );
    return response.data;
  },

  // Organizer profile
  async getOrganizerProfile(id: number): Promise<OrganizerProfile> {
    const response = await api.get<OrganizerProfile>(`/api/organizers/${id}`);
    return response.data;
  },

  async updateOrganizerProfile(data: Partial<OrganizerProfile>): Promise<OrganizerProfile> {
    const response = await api.put<OrganizerProfile>('/api/organizers/me/profile', data);
    return response.data;
  },

  // Tags
  async getAllTags(): Promise<Tag[]> {
    const response = await api.get<{ items: Tag[] }>('/api/tags');
    return response.data.items;
  },

  // Metadata
  async getUniversityCatalog(): Promise<UniversityCatalogItem[]> {
    const response = await api.get<{ items: UniversityCatalogItem[] }>('/api/metadata/universities');
    return response.data.items;
  },

  // Student profile
  async getStudentProfile(): Promise<StudentProfile> {
    const response = await api.get<StudentProfile>('/api/me/profile');
    return response.data;
  },

  async updateStudentProfile(data: StudentProfileUpdate): Promise<StudentProfile> {
    const response = await api.put<StudentProfile>('/api/me/profile', data);
    return response.data;
  },

  // Personalization controls (students)
  async getPersonalizationSettings(): Promise<PersonalizationSettings> {
    const response = await api.get<PersonalizationSettings>('/api/me/personalization');
    return response.data;
  },

  async hideTag(tagId: number): Promise<void> {
    await api.post(`/api/me/personalization/hidden-tags/${tagId}`);
  },

  async unhideTag(tagId: number): Promise<void> {
    await api.delete(`/api/me/personalization/hidden-tags/${tagId}`);
  },

  async blockOrganizer(organizerId: number): Promise<void> {
    await api.post(`/api/me/personalization/blocked-organizers/${organizerId}`);
  },

  async unblockOrganizer(organizerId: number): Promise<void> {
    await api.delete(`/api/me/personalization/blocked-organizers/${organizerId}`);
  },

  // Notification preferences (students)
  async getNotificationPreferences(): Promise<NotificationPreferences> {
    const response = await api.get<NotificationPreferences>('/api/me/notifications');
    return response.data;
  },

  async updateNotificationPreferences(
    payload: NotificationPreferencesUpdate,
  ): Promise<NotificationPreferences> {
    const response = await api.put<NotificationPreferences>('/api/me/notifications', payload);
    return response.data;
  },

  // Organizer assist
  async suggestEvent(payload: EventSuggestRequest): Promise<EventSuggestResponse> {
    const response = await api.post<EventSuggestResponse>('/api/organizer/events/suggest', payload);
    return response.data;
  },
};

export default eventService;
