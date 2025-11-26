import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EventDetail } from '../models';
import { EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';
import { TranslatePipe } from '../pipes/translate.pipe';
import { TranslationService } from '../services/translation.service';
import { NotificationService } from '../services/notification.service';

@Component({
  selector: 'app-event-details',
  standalone: true,
  imports: [CommonModule, RouterLink, DatePipe, TranslatePipe],
  templateUrl: './event-details.component.html',
  styleUrl: './event-details.component.scss',
})
export class EventDetailsComponent implements OnInit {
  event?: EventDetail;
  error = '';
  loading = true;
  successMessage = '';
  placeholderCover = '/assets/cover-placeholder.svg';
  actionLoading = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private eventService: EventService,
    public auth: AuthService,
    private i18n: TranslationService,
    private notifications: NotificationService,
  ) {}

  icsLink(eventId: number): string {
    return `${this.eventService.baseApiUrl}/api/events/${eventId}/ics`;
  }

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
        this.error = this.i18n.translate('errors.generic');
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
    this.actionLoading = true;
    this.eventService.registerForEvent(this.event.id).subscribe({
      next: () => {
        this.event!.is_registered = true;
        this.event!.seats_taken += 1;
        if (this.event!.available_seats !== undefined && this.event!.available_seats !== null) {
          this.event!.available_seats -= 1;
        }
        this.successMessage = this.i18n.translate('details.register');
        this.notifications.success(this.i18n.translate('toasts.registered'));
        this.error = '';
        this.actionLoading = false;
      },
      error: (err) => {
        if (err.status === 409) {
          this.error = this.i18n.translate('details.full');
        } else {
          this.error = err.error?.detail || this.i18n.translate('errors.generic');
        }
        this.notifications.error(this.error);
        this.actionLoading = false;
      },
    });
  }

  unregister(): void {
    if (!this.event) return;
    this.actionLoading = true;
    this.eventService.unregisterFromEvent(this.event.id).subscribe({
      next: () => {
        this.event!.is_registered = false;
        if (this.event!.seats_taken > 0) {
          this.event!.seats_taken -= 1;
        }
        if (this.event!.available_seats !== undefined && this.event!.available_seats !== null) {
          this.event!.available_seats += 1;
        }
        this.successMessage = this.i18n.translate('details.unregister');
        this.notifications.success(this.i18n.translate('toasts.unregistered'));
        this.error = '';
        this.actionLoading = false;
      },
      error: (err) => {
        this.error = err.error?.detail || this.i18n.translate('errors.generic');
        this.notifications.error(this.error);
        this.actionLoading = false;
      },
    });
  }

  deleteEvent(): void {
    if (!this.event) return;
    const confirmed = confirm('Ești sigur? Acțiunea este ireversibilă.');
    if (!confirmed) return;
    this.eventService.deleteEvent(this.event.id).subscribe({
      next: () => this.router.navigate(['/organizer/events']),
      error: () => (this.error = this.i18n.translate('errors.generic')),
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
