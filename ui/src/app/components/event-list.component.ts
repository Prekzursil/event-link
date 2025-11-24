import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EventService, EventSummary } from '../services/event.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="filters">
      <input [(ngModel)]="search" (ngModelChange)="loadEvents()" placeholder="Caută..." />
      <select [(ngModel)]="category" (change)="loadEvents()">
        <option value="">Toate categoriile</option>
        <option *ngFor="let c of categories" [value]="c">{{ c }}</option>
      </select>
      <label>Start</label>
      <input type="date" [(ngModel)]="start_date" (change)="loadEvents()" />
      <label>End</label>
      <input type="date" [(ngModel)]="end_date" (change)="loadEvents()" />
      <button (click)="resetFilters()">Reset</button>
    </section>

    <section *ngIf="recommended.length" class="recommended">
      <h3>Recomandate pentru tine</h3>
      <div class="card" *ngFor="let event of recommended">
        <a [routerLink]="['/events', event.id]">{{ event.title }}</a>
        <div>{{ event.event_date | date }}</div>
      </div>
    </section>

    <section>
      <h3>Evenimente</h3>
      <div *ngIf="events.length === 0">Momentan nu sunt evenimente viitoare.</div>
      <div class="card" *ngFor="let event of events">
        <a [routerLink]="['/events', event.id]">{{ event.title }}</a>
        <div>{{ event.event_date | date }} - {{ event.location }}</div>
        <div>{{ event.registrations_count }} / {{ event.max_seats || '∞' }}</div>
      </div>
    </section>
  `,
})
export class EventListComponent implements OnInit {
  events: EventSummary[] = [];
  recommended: EventSummary[] = [];
  categories = ['academic', 'social', 'sports', 'other'];
  search = '';
  category = '';
  start_date = '';
  end_date = '';

  constructor(private eventsApi: EventService, private auth: AuthService) {}

  ngOnInit(): void {
    this.loadEvents();
    if (this.auth.isStudent()) {
      this.eventsApi.recommended().subscribe((data) => (this.recommended = data));
    }
  }

  loadEvents() {
    this.eventsApi
      .list({ search: this.search, category: this.category, start_date: this.start_date, end_date: this.end_date })
      .subscribe((data) => (this.events = data));
  }

  resetFilters() {
    this.search = '';
    this.category = '';
    this.start_date = '';
    this.end_date = '';
    this.loadEvents();
  }
}
