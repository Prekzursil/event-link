import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormArray, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { EventService } from '../services/event.service';

@Component({
  selector: 'app-event-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <h2>{{ isEdit ? 'Editare' : 'Creează eveniment' }}</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <label>Titlu</label>
      <input formControlName="title" />
      <label>Descriere</label>
      <textarea formControlName="description"></textarea>
      <label>Categorie</label>
      <input formControlName="category" />
      <label>Data</label>
      <input type="date" formControlName="event_date" />
      <label>Start</label>
      <input type="datetime-local" formControlName="start_time" />
      <label>End</label>
      <input type="datetime-local" formControlName="end_time" />
      <label>Locație</label>
      <input formControlName="location" />
      <label>Locuri maxime</label>
      <input type="number" formControlName="max_seats" />
      <label>Tags</label>
      <div>
        <input #tagInput />
        <button type="button" (click)="addTag(tagInput.value); tagInput.value=''">Adaugă</button>
        <div class="tag" *ngFor="let tag of tags.controls; let i = index">
          {{ tag.value }} <button type="button" (click)="removeTag(i)">x</button>
        </div>
      </div>
      <button type="submit" [disabled]="form.invalid">Salvează</button>
      <div class="error" *ngIf="error">{{ error }}</div>
    </form>
  `,
})
export class EventFormComponent implements OnInit {
  error = '';
  isEdit = false;
  eventId?: number;
  form = this.fb.group({
    title: ['', Validators.required],
    description: ['', Validators.required],
    category: ['', Validators.required],
    event_date: ['', Validators.required],
    start_time: ['', Validators.required],
    end_time: [''],
    location: ['', Validators.required],
    max_seats: [10, [Validators.required, Validators.min(1)]],
    tags: this.fb.array<string>([]),
  });

  get tags() {
    return this.form.get('tags') as FormArray;
  }

  constructor(private fb: FormBuilder, private eventsApi: EventService, private router: Router, private route: ActivatedRoute) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEdit = true;
      this.eventId = Number(id);
      this.eventsApi.get(this.eventId).subscribe((evt) => {
        this.form.patchValue({
          title: evt.title,
          description: evt.description,
          category: evt.category,
          event_date: evt.event_date.substring(0, 10),
          start_time: evt.start_time.substring(0, 16),
          end_time: evt.end_time ? evt.end_time.substring(0, 16) : '',
          location: evt.location,
          max_seats: evt.max_seats,
        });
        evt.tags.forEach((t) => this.tags.push(this.fb.control(t.name)));
      });
    }
  }

  addTag(value: string) {
    if (value.trim()) {
      this.tags.push(this.fb.control(value.trim()));
    }
  }

  removeTag(index: number) {
    this.tags.removeAt(index);
  }

  onSubmit() {
    if (this.form.invalid) return;
    const payload = { ...this.form.value, tags: this.tags.value };
    if (this.isEdit && this.eventId) {
      this.eventsApi.update(this.eventId, payload).subscribe({
        next: (evt) => this.router.navigate(['/events', evt.id]),
        error: (err) => (this.error = err.error?.detail || 'Eroare la salvare'),
      });
    } else {
      this.eventsApi.create(payload).subscribe({
        next: (evt) => this.router.navigate(['/events', evt.id]),
        error: (err) => (this.error = err.error?.detail || 'Eroare la salvare'),
      });
    }
  }
}
