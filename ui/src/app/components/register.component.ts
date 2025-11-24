import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <h2>Creează cont</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <label>Email</label>
      <input formControlName="email" type="email" />
      <label>Parolă</label>
      <input formControlName="password" type="password" />
      <label>Confirmă parola</label>
      <input formControlName="confirm_password" type="password" />
      <label>Rol</label>
      <select formControlName="role">
        <option value="student">Student</option>
        <option value="organizer">Organizer</option>
      </select>
      <button type="submit" [disabled]="form.invalid">Creează cont</button>
      <div class="error" *ngIf="error">{{ error }}</div>
    </form>
  `,
})
export class RegisterComponent {
  error = '';
  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', [Validators.required]],
    role: ['student', Validators.required],
  });

  constructor(private fb: FormBuilder, private auth: AuthService, private router: Router) {}

  onSubmit() {
    if (this.form.invalid) return;
    const { email, password, confirm_password, role } = this.form.value;
    if (password !== confirm_password) {
      this.error = 'Parolele nu se potrivesc.';
      return;
    }
    this.auth.register(email!, password!, confirm_password!, role as any).subscribe({
      next: (resp) => {
        this.auth.saveSession(resp);
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error = err.error?.detail || 'Acest email este deja folosit.';
      },
    });
  }
}
