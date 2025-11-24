import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';

export interface EventSummary {
  id: number;
  title: string;
  category?: string;
  event_date: string;
  start_time: string;
  end_time?: string;
  location?: string;
  max_seats?: number;
  registrations_count: number;
}

export interface EventDetail extends EventSummary {
  description?: string;
  owner_id: number;
  tags: { id: number; name: string }[];
}

@Injectable({ providedIn: 'root' })
export class EventService {
  private baseUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient, private auth: AuthService) {}

  list(params: { search?: string; category?: string; start_date?: string; end_date?: string }): Observable<EventSummary[]> {
    let httpParams = new HttpParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        httpParams = httpParams.set(key, value);
      }
    });
    return this.http.get<EventSummary[]>(`${this.baseUrl}/events`, { params: httpParams });
  }

  get(id: number) {
    return this.http.get<EventDetail>(`${this.baseUrl}/events/${id}`);
  }

  create(event: any) {
    return this.http.post<EventDetail>(`${this.baseUrl}/events`, event);
  }

  update(id: number, event: any) {
    return this.http.put<EventDetail>(`${this.baseUrl}/events/${id}`, event);
  }

  delete(id: number) {
    return this.http.delete(`${this.baseUrl}/events/${id}`);
  }

  register(eventId: number) {
    return this.http.post(`${this.baseUrl}/events/${eventId}/register`, {});
  }

  myRegistrations() {
    return this.http.get<EventSummary[]>(`${this.baseUrl}/my-registrations`);
  }

  organizerEvents() {
    return this.http.get<EventSummary[]>(`${this.baseUrl}/organizer/events`);
  }

  participants(eventId: number) {
    return this.http.get<any>(`${this.baseUrl}/events/${eventId}/participants`);
  }

  recommended() {
    return this.http.get<EventSummary[]>(`${this.baseUrl}/recommended`);
  }
}
