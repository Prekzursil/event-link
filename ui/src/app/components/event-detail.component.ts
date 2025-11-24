import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { EventDetail, EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <ng-container *ngIf="event">
      <h2>{{ event.title }}</h2>
      <div>{{ event.description }}</div>
      <div>{{ event.event_date | date: 'mediumDate' }} {{ event.start_time | date: 'shortTime' }}</div>
      <div>{{ event.location }}</div>
      <div>Locuri: {{ event.registrations_count }} / {{ event.max_seats || '∞' }}</div>
      <div class="tags">
        <span class="tag" *ngFor="let tag of event.tags">{{ tag.name }}</span>
      </div>
      <button *ngIf="auth.isStudent()" [disabled]="isFull || isRegistered" (click)="register()">
        {{ isRegistered ? 'Înscris' : isFull ? 'Eveniment plin' : 'Înscrie-te' }}
      </button>
      <div class="error" *ngIf="error">{{ error }}</div>
      <div *ngIf="auth.isOrganizer() && ownsEvent">
        <a [routerLink]="['/edit', event.id]">Editare</a>
      </div>
    </ng-container>
  `,
})
export class EventDetailComponent implements OnInit {
  event?: EventDetail;
  isFull = false;
  isRegistered = false;
  error = '';
  ownsEvent = false;

  constructor(private route: ActivatedRoute, private eventsApi: EventService, public auth: AuthService) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.load(id);
  }

  load(id: number) {
    this.eventsApi.get(id).subscribe((evt) => {
      this.event = evt;
      this.isFull = evt.max_seats ? evt.registrations_count >= evt.max_seats : false;
      this.ownsEvent = this.auth.currentUser()?.id === evt.owner_id;
    });
  }

  register() {
    if (!this.event) return;
    if (!this.auth.currentUser()) {
      this.error = 'Autentifică-te pentru a te înscrie.';
      return;
    }
    this.eventsApi.register(this.event.id).subscribe({
      next: () => {
        this.isRegistered = true;
        this.event!.registrations_count += 1;
      },
      error: (err) => (this.error = err.error?.detail || 'Ne pare rău, toate locurile au fost ocupate.'),
    });
  }
}
