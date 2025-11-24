import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <h2>Autentificare</h2>
    <form [formGroup]="form" (ngSubmit)="onSubmit()">
      <label>Email</label>
      <input formControlName="email" type="email" />
      <label>Parolă</label>
      <input formControlName="password" type="password" />
      <button type="submit" [disabled]="form.invalid">Autentificare</button>
      <div class="error" *ngIf="error">{{ error }}</div>
    </form>
  `,
})
export class LoginComponent {
  error = '';
  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  constructor(private fb: FormBuilder, private auth: AuthService, private router: Router) {}

  onSubmit() {
    if (this.form.invalid) return;
    this.auth.login(this.form.value.email!, this.form.value.password!).subscribe({
      next: (resp) => {
        this.auth.saveSession(resp);
        this.router.navigate(['/']);
      },
      error: () => (this.error = 'Email sau parolă incorectă'),
    });
  }
}
