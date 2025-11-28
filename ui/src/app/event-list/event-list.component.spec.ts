import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { EventListComponent } from './event-list.component';
import { EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';
import { of } from 'rxjs';
import { ActivatedRoute } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';

const eventsMock = {
  items: [
    {
      id: 1,
      title: 'Test event',
      description: '',
      category: 'Cat',
      start_time: new Date().toISOString(),
      end_time: null,
      location: 'Loc',
      max_seats: 10,
      owner_id: 1,
      owner_name: 'Org',
      tags: [],
      seats_taken: 0,
      cover_url: null,
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

describe('EventListComponent', () => {
  let component: EventListComponent;
  let fixture: ComponentFixture<EventListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EventListComponent, RouterTestingModule],
      providers: [
        { provide: EventService, useValue: { listEvents: () => of(eventsMock), recommended: () => of([]) } },
        { provide: AuthService, useValue: { isStudent: () => false, currentUser$: of(null) } },
        { provide: ActivatedRoute, useValue: { queryParams: of({}) } },
      ],
      schemas: [NO_ERRORS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(EventListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should render event title', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test event');
  });
});
