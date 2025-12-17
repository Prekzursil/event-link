import api from './api';
import type { 
  Event, 
  EventDetail, 
  PaginatedEvents, 
  EventFilters, 
  EventFormData,
  ParticipantList,
  OrganizerProfile,
  Tag,
  StudentProfile,
  StudentProfileUpdate,
} from '../types';

export const eventService = {
  // Public event endpoints
  async getEvents(filters: EventFilters = {}): Promise<PaginatedEvents> {
    const params = new URLSearchParams();
    
    if (filters.search) params.append('search', filters.search);
    if (filters.category) params.append('category', filters.category);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.location) params.append('location', filters.location);
    if (filters.include_past) params.append('include_past', 'true');
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.tags?.length) {
      params.append('tags_csv', filters.tags.join(','));
    }

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

  // Student profile
  async getStudentProfile(): Promise<StudentProfile> {
    const response = await api.get<StudentProfile>('/api/me/profile');
    return response.data;
  },

  async updateStudentProfile(data: StudentProfileUpdate): Promise<StudentProfile> {
    const response = await api.put<StudentProfile>('/api/me/profile', data);
    return response.data;
  },
};

export default eventService;
