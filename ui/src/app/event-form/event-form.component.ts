import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EventService, EventPayload } from '../services/event.service';
import { AuthService } from '../services/auth.service';
import { EventDetail } from '../models';

@Component({
  selector: 'app-event-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './event-form.component.html',
  styleUrl: './event-form.component.scss',
})
export class EventFormComponent implements OnInit {
  form!: FormGroup;
  tags: string[] = [];
  editMode = false;
  eventId?: number;
  error = '';
  title = 'Creează eveniment';

  constructor(
    private fb: FormBuilder,
    private eventService: EventService,
    private route: ActivatedRoute,
    private router: Router,
    public auth: AuthService
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      title: ['', [Validators.required]],
      description: ['', [Validators.required, Validators.minLength(10)]],
      category: ['', Validators.required],
      date: ['', Validators.required],
      startTime: ['', Validators.required],
      endTime: [''],
      location: ['', Validators.required],
      maxSeats: [50, [Validators.required, Validators.min(1)]],
      tagInput: [''],
      coverUrl: [''],
    });

    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.editMode = true;
      this.eventId = Number(id);
      this.title = 'Editează eveniment';
      this.loadEvent(this.eventId);
    }
  }

  loadEvent(id: number): void {
    this.eventService.getEvent(id).subscribe({
      next: (event: EventDetail) => {
        const start = new Date(event.start_time);
        const end = event.end_time ? new Date(event.end_time) : undefined;
        const startTime = `${start.getHours().toString().padStart(2, '0')}:${start.getMinutes()
          .toString()
          .padStart(2, '0')}`;
        const endTime = end
          ? `${end.getHours().toString().padStart(2, '0')}:${end.getMinutes().toString().padStart(2, '0')}`
          : '';
        this.form.patchValue({
          title: event.title,
          description: event.description,
          category: event.category,
          date: event.start_time?.substring(0, 10),
          startTime,
          endTime,
          location: event.location,
          maxSeats: event.max_seats,
          coverUrl: event.cover_url,
        });
        this.tags = event.tags.map((t) => t.name);
      },
      error: () => {
        this.error = 'Nu am putut încărca evenimentul.';
      },
    });
  }

  addTag(): void {
    const value = (this.form.get('tagInput')?.value as string)?.trim();
    if (value) {
      this.tags.push(value);
      this.form.get('tagInput')?.setValue('');
    }
  }

  removeTag(tag: string): void {
    this.tags = this.tags.filter((t) => t !== tag);
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { title, description, category, date, startTime, endTime, location, maxSeats, coverUrl } = this.form.value;
    const start = new Date(`${date}T${startTime}`);
    const end = endTime ? new Date(`${date}T${endTime}`) : undefined;
    const now = new Date();
    if (start < now) {
      this.error = 'Data evenimentului nu poate fi în trecut.';
      return;
    }
    if (end && end <= start) {
      this.error = 'Ora de sfârșit trebuie să fie după ora de început.';
      return;
    }

    const payload: EventPayload = {
      title,
      description,
      category,
      start_time: start.toISOString(),
      end_time: end ? end.toISOString() : undefined,
      location,
      max_seats: Number(maxSeats),
      tags: this.tags,
      cover_url: coverUrl || undefined,
    };

    if (this.editMode && this.eventId) {
      this.eventService.updateEvent(this.eventId, payload).subscribe({
        next: (event) => this.router.navigate(['/events', event.id]),
        error: (err) => (this.error = err.error?.detail || 'Nu am putut salva modificările.'),
      });
    } else {
      this.eventService.createEvent(payload).subscribe({
        next: (event) => this.router.navigate(['/events', event.id]),
        error: (err) => (this.error = err.error?.detail || 'Nu am putut crea evenimentul.'),
      });
    }
  }
}
