import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EventItem } from '../models';
import { EventService } from '../services/event.service';

@Component({
  selector: 'app-organizer-events',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe],
  templateUrl: './organizer-events.component.html',
  styleUrl: './organizer-events.component.scss',
})
export class OrganizerEventsComponent implements OnInit {
  events: EventItem[] = [];
  error = '';

  constructor(private eventService: EventService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.eventService.organizerEvents().subscribe({
      next: (events) => (this.events = events),
      error: () => (this.error = 'Nu am putut încărca evenimentele create.'),
    });
  }

  delete(event: EventItem, event_: Event): void {
    event_.stopPropagation();
    const confirmed = confirm('Ești sigur că vrei să ștergi evenimentul?');
    if (!confirmed) return;
    this.eventService.deleteEvent(event.id).subscribe({
      next: () => this.load(),
      error: () => (this.error = 'Nu am putut șterge evenimentul.'),
    });
  }

  clone(event: EventItem, event_: Event): void {
    event_.stopPropagation();
    this.eventService.cloneEvent(event.id).subscribe({
      next: () => this.load(),
      error: () => (this.error = 'Nu am putut clona evenimentul.'),
    });
  }

  seatsLabel(event: EventItem): string {
    if (!event.max_seats) return `${event.seats_taken} locuri ocupate`;
    return `${event.seats_taken} / ${event.max_seats}`;
  }
}
