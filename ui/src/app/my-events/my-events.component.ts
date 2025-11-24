import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EventItem } from '../models';
import { EventService } from '../services/event.service';

@Component({
  selector: 'app-my-events',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe],
  templateUrl: './my-events.component.html',
  styleUrl: './my-events.component.scss',
})
export class MyEventsComponent implements OnInit {
  events: EventItem[] = [];
  error = '';

  constructor(private eventService: EventService) {}

  ngOnInit(): void {
    this.eventService.myEvents().subscribe({
      next: (events) => (this.events = events),
      error: () => (this.error = 'Nu am putut încărca evenimentele mele.'),
    });
  }
}
