import { Inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { EventDetail, EventItem, ParticipantList, PaginatedEvents } from '../models';
import { API_BASE_URL } from '../api-tokens';

export interface EventPayload {
  title: string;
  description?: string;
  category: string;
  start_time: string;
  end_time?: string;
  location: string;
  max_seats: number;
  tags: string[];
  cover_url?: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class EventService {
  private readonly baseUrl: string;

  constructor(private http: HttpClient, @Inject(API_BASE_URL) apiBaseUrl: string) {
    this.baseUrl = `${apiBaseUrl}/api`;
  }

  listEvents(filters?: {
    search?: string;
    category?: string;
    start_date?: string | null;
    end_date?: string | null;
    page?: number;
    page_size?: number;
  }): Observable<PaginatedEvents> {
    let params = new HttpParams();
    if (filters?.search) params = params.set('search', filters.search);
    if (filters?.category) params = params.set('category', filters.category);
    if (filters?.start_date) params = params.set('start_date', filters.start_date);
    if (filters?.end_date) params = params.set('end_date', filters.end_date);
    if (filters?.page) params = params.set('page', filters.page);
    if (filters?.page_size) params = params.set('page_size', filters.page_size);
    return this.http.get<PaginatedEvents>(`${this.baseUrl}/events`, { params });
  }

  recommended(): Observable<EventItem[]> {
    return this.http.get<EventItem[]>(`${this.baseUrl}/recommendations`);
  }

  getEvent(id: number): Observable<EventDetail> {
    return this.http.get<EventDetail>(`${this.baseUrl}/events/${id}`);
  }

  createEvent(payload: EventPayload): Observable<EventItem> {
    return this.http.post<EventItem>(`${this.baseUrl}/events`, payload);
  }

  updateEvent(id: number, payload: Partial<EventPayload>): Observable<EventItem> {
    return this.http.put<EventItem>(`${this.baseUrl}/events/${id}`, payload);
  }

  deleteEvent(id: number) {
    return this.http.delete(`${this.baseUrl}/events/${id}`);
  }

  registerForEvent(id: number) {
    return this.http.post(`${this.baseUrl}/events/${id}/register`, {});
  }

  unregisterFromEvent(id: number) {
    return this.http.delete(`${this.baseUrl}/events/${id}/register`);
  }

  organizerEvents(): Observable<EventItem[]> {
    return this.http.get<EventItem[]>(`${this.baseUrl}/organizer/events`);
  }

  participants(eventId: number): Observable<ParticipantList> {
    return this.http.get<ParticipantList>(`${this.baseUrl}/organizer/events/${eventId}/participants`);
  }

  myEvents(): Observable<EventItem[]> {
    return this.http.get<EventItem[]>(`${this.baseUrl}/me/events`);
  }
}
