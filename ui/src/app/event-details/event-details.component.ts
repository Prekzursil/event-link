import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EventDetail } from '../models';
import { EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-event-details',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe],
  templateUrl: './event-details.component.html',
  styleUrl: './event-details.component.scss',
})
export class EventDetailsComponent implements OnInit {
  event?: EventDetail;
  error = '';
  loading = true;
  successMessage = '';
  placeholderCover = '/assets/cover-placeholder.svg';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private eventService: EventService,
    public auth: AuthService
  ) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (id) {
      this.loadEvent(id);
    }
  }

  loadEvent(id: number): void {
    this.loading = true;
    this.eventService.getEvent(id).subscribe({
      next: (event) => {
        this.event = event;
        this.loading = false;
      },
      error: () => {
        this.error = 'Evenimentul nu există sau nu mai este disponibil.';
        this.loading = false;
      },
    });
  }

  register(): void {
    if (!this.event) return;
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { redirect: this.router.url } });
      return;
    }
    this.eventService.registerForEvent(this.event.id).subscribe({
      next: () => {
        this.event!.is_registered = true;
        this.event!.seats_taken += 1;
        if (this.event!.available_seats !== undefined && this.event!.available_seats !== null) {
          this.event!.available_seats -= 1;
        }
        this.successMessage = 'Înscriere confirmată!';
        this.error = '';
      },
      error: (err) => {
        if (err.status === 409) {
          this.error = 'Ne pare rău, toate locurile au fost ocupate.';
        } else {
          this.error = err.error?.detail || 'Nu am putut procesa înscrierea.';
        }
      },
    });
  }

  unregister(): void {
    if (!this.event) return;
    this.eventService.unregisterFromEvent(this.event.id).subscribe({
      next: () => {
        this.event!.is_registered = false;
        if (this.event!.seats_taken > 0) {
          this.event!.seats_taken -= 1;
        }
        if (this.event!.available_seats !== undefined && this.event!.available_seats !== null) {
          this.event!.available_seats += 1;
        }
        this.successMessage = 'Te-ai dezabonat de la eveniment.';
        this.error = '';
      },
      error: (err) => {
        this.error = err.error?.detail || 'Nu am putut anula înscrierea.';
      },
    });
  }

  deleteEvent(): void {
    if (!this.event) return;
    const confirmed = confirm('Ești sigur? Acțiunea este ireversibilă.');
    if (!confirmed) return;
    this.eventService.deleteEvent(this.event.id).subscribe({
      next: () => this.router.navigate(['/organizer/events']),
      error: () => (this.error = 'Nu am putut șterge evenimentul.'),
    });
  }

  canRegister(): boolean {
    if (!this.event) return false;
    if (!this.auth.isStudent()) return false;
    if (this.event.is_registered) return false;
    if (this.event.available_seats !== undefined && this.event.available_seats !== null && this.event.available_seats <= 0)
      return false;
    return true;
  }

  onCoverError(): void {
    if (this.event) {
      this.event.cover_url = this.placeholderCover;
    }
  }
}
