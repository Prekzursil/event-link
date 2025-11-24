import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { EventService, EventSummary } from '../services/event.service';

@Component({
  selector: 'app-organizer-events',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <h2>Evenimente create</h2>
    <div *ngFor="let event of events" class="card">
      <div>
        <a [routerLink]="['/events', event.id]">{{ event.title }}</a>
        <div>{{ event.event_date | date }}</div>
        <div>{{ event.registrations_count }} / {{ event.max_seats || '∞' }}</div>
      </div>
      <div class="actions">
        <a [routerLink]="['/edit', event.id]">Edit</a>
        <a [routerLink]="['/events', event.id, 'participants']">Participanți</a>
      </div>
    </div>
  `,
})
export class OrganizerEventsComponent implements OnInit {
  events: EventSummary[] = [];

  constructor(private eventsApi: EventService) {}

  ngOnInit(): void {
    this.eventsApi.organizerEvents().subscribe((data) => (this.events = data));
  }
}
