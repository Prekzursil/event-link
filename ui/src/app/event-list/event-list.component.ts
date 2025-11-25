import { CommonModule, DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { EventService } from '../services/event.service';
import { EventItem } from '../models';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, DatePipe],
  templateUrl: './event-list.component.html',
  styleUrl: './event-list.component.scss',
})
export class EventListComponent implements OnInit {
  events: EventItem[] = [];
  recommended: EventItem[] = [];
  categories: string[] = [];
  searchText = '';
  categoryFilter = '';
  startDate: string | null = null;
  endDate: string | null = null;
  page = 1;
  pageSize = 10;
  total = 0;
  loading = false;
  errorMessage = '';
  placeholderCover = '/assets/cover-placeholder.svg';

  constructor(
    private eventService: EventService,
    public auth: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.route.queryParams.subscribe((params) => {
      this.searchText = params['search'] || '';
      this.categoryFilter = params['category'] || '';
      this.startDate = params['start_date'] || null;
      this.endDate = params['end_date'] || null;
      this.page = params['page'] ? Number(params['page']) : 1;
      this.pageSize = params['page_size'] ? Number(params['page_size']) : 10;
      this.fetchEvents();
    });
    if (this.auth.isStudent()) {
      this.loadRecommended();
    }
    this.auth.currentUser$.subscribe((user) => {
      if (user && this.auth.isStudent()) {
        this.loadRecommended();
      }
    });
  }

  fetchEvents(): void {
    this.loading = true;
    this.eventService
      .listEvents({
        search: this.searchText || undefined,
        category: this.categoryFilter || undefined,
        start_date: this.startDate,
        end_date: this.endDate,
        page: this.page,
        page_size: this.pageSize,
      })
      .subscribe({
        next: (result) => {
          this.events = result.items;
          this.total = result.total;
          this.page = result.page;
          this.pageSize = result.page_size;
          this.categories = Array.from(new Set(result.items.map((e) => e.category).filter((c): c is string => !!c)));
          this.loading = false;
        },
        error: () => {
          this.errorMessage = 'Nu am putut încărca evenimentele.';
          this.loading = false;
        },
      });
  }

  loadRecommended(): void {
    this.eventService.recommended().subscribe({
      next: (events) => (this.recommended = events),
      error: () => (this.recommended = []),
    });
  }

  resetFilters(): void {
    this.searchText = '';
    this.categoryFilter = '';
    this.startDate = null;
    this.endDate = null;
    this.page = 1;
    this.navigateWithFilters();
  }

  onSearchChange(): void {
    this.page = 1;
    this.navigateWithFilters();
  }

  get totalPages(): number {
    return this.pageSize > 0 ? Math.max(1, Math.ceil(this.total / this.pageSize)) : 1;
  }

  changePageSize(size: number): void {
    this.pageSize = size;
    this.page = 1;
    this.navigateWithFilters();
  }

  changePage(delta: number): void {
    const newPage = this.page + delta;
    if (newPage < 1 || (this.total && (newPage - 1) * this.pageSize >= this.total)) {
      return;
    }
    this.page = newPage;
    this.navigateWithFilters();
  }

  openEvent(event: EventItem): void {
    this.router.navigate(['/events', event.id]);
  }

  seatsLabel(event: EventItem): string {
    if (!event.max_seats) return `${event.seats_taken} locuri ocupate`;
    return `${event.seats_taken} / ${event.max_seats} locuri`;
  }

  onCoverError(eventItem: EventItem): void {
    eventItem.cover_url = this.placeholderCover;
  }

  onFiltersChange(): void {
    this.page = 1;
    this.navigateWithFilters();
  }

  private navigateWithFilters(): void {
    const queryParams: Record<string, any> = {
      search: this.searchText || null,
      category: this.categoryFilter || null,
      start_date: this.startDate || null,
      end_date: this.endDate || null,
      page: this.page !== 1 ? this.page : null,
      page_size: this.pageSize !== 10 ? this.pageSize : null,
    };
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }
}
