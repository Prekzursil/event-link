import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

export interface User {
  id: number;
  email: string;
  role: 'student' | 'organizer' | 'organizator';
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private baseUrl = 'http://localhost:8000';
  currentUser = signal<User | null>(null);
  token = signal<string | null>(null);

  constructor(private http: HttpClient, private router: Router) {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    if (token && user) {
      this.token.set(token);
      this.currentUser.set(JSON.parse(user));
    }
  }

  login(email: string, password: string) {
    return this.http.post<AuthResponse>(`${this.baseUrl}/login`, { email, password });
  }

  register(email: string, password: string, confirm_password: string, role: 'student' | 'organizer' | 'organizator') {
    return this.http.post<AuthResponse>(`${this.baseUrl}/register`, {
      email,
      password,
      confirm_password,
      role
    });
  }

  saveSession(resp: AuthResponse) {
    this.token.set(resp.access_token);
    this.currentUser.set(resp.user);
    localStorage.setItem('token', resp.access_token);
    localStorage.setItem('user', JSON.stringify(resp.user));
  }

  logout() {
    this.token.set(null);
    this.currentUser.set(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    this.router.navigate(['/login']);
  }

  isOrganizer() {
    return this.currentUser()?.role === 'organizer' || this.currentUser()?.role === 'organizator';
  }

  isStudent() {
    return this.currentUser()?.role === 'student';
  }
}
