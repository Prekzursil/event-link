import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { HttpClient } from '@angular/common/http';
import { API_BASE_URL } from '../api-tokens';
import { Inject } from '@angular/core';

@Component({
  selector: 'app-organizer-upgrade',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <section class="card auth-card">
      <h1>Devino organizator</h1>
      <p class="muted">Introdu codul de invitație furnizat de admin pentru a activa rolul de organizator.</p>
      <form [formGroup]="form" (ngSubmit)="submit()">
        <div class="field">
          <label>Cod invitație</label>
          <input formControlName="code" type="text" />
        </div>
        <button class="btn primary" type="submit" [disabled]="loading">Activează</button>
        <div class="error" *ngIf="error">{{ error }}</div>
        <div class="success" *ngIf="success">Rolul de organizator a fost activat.</div>
      </form>
    </section>
  `,
})
export class OrganizerUpgradeComponent {
  form: FormGroup;
  loading = false;
  error = '';
  success = false;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private auth: AuthService,
    private router: Router,
    @Inject(API_BASE_URL) private baseUrl: string
  ) {
    this.form = this.fb.group({
      code: ['', Validators.required],
    });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading = true;
    this.error = '';
    this.success = false;
    this.http
      .post(`${this.baseUrl}/organizer/upgrade`, { invite_code: this.form.value.code })
      .subscribe({
        next: () => {
          this.loading = false;
          this.success = true;
          this.auth.loadProfile().subscribe(() => this.router.navigate(['/organizer/events']));
        },
        error: (err) => {
          this.loading = false;
          this.error = err.error?.detail || 'Cod invalid sau acces interzis';
        },
      });
  }
}
