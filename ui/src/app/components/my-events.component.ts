import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { EventService, EventSummary } from '../services/event.service';

@Component({
  selector: 'app-my-events',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <h2>Evenimentele mele</h2>
    <div *ngIf="events.length === 0">Nu ești înscris la niciun eveniment.</div>
    <div class="card" *ngFor="let event of events">
      <a [routerLink]="['/events', event.id]">{{ event.title }}</a>
      <div>{{ event.event_date | date }}</div>
    </div>
  `,
})
export class MyEventsComponent implements OnInit {
  events: EventSummary[] = [];

  constructor(private eventsApi: EventService) {}

  ngOnInit(): void {
    this.eventsApi.myRegistrations().subscribe((data) => (this.events = data));
  }
}
