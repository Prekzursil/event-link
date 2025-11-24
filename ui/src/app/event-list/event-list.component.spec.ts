import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EventListComponent } from './event-list.component';
import { EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';
import { of } from 'rxjs';

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
      imports: [EventListComponent],
      providers: [
        { provide: EventService, useValue: { listEvents: () => of(eventsMock), recommended: () => of([]) } },
        { provide: AuthService, useValue: { isStudent: () => false, currentUser$: of(null) } },
      ],
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
