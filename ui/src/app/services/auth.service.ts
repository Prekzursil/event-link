import { Inject, Injectable } from '@angular/core';
import { BehaviorSubject, Observable, switchMap, tap } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { AuthToken, User } from '../models';
import { API_BASE_URL } from '../api-tokens';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly baseUrl: string;
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient, @Inject(API_BASE_URL) baseUrl: string) {
    this.baseUrl = baseUrl;
    this.restoreSession();
  }

  get token(): string | null {
    return localStorage.getItem('token');
  }

  get role(): string | null {
    return this.currentUserSubject.value?.role ?? localStorage.getItem('role');
  }

  isStudent(): boolean {
    return this.role === 'student';
  }

  isOrganizer(): boolean {
    return this.role === 'organizator';
  }

  isLoggedIn(): boolean {
    return !!this.token;
  }

  login(email: string, password: string): Observable<User> {
    return this.http.post<AuthToken>(`${this.baseUrl}/login`, { email, password }).pipe(
      tap((token) => this.persistToken(token)),
      switchMap(() => this.loadProfile())
    );
  }

  register(email: string, password: string, confirmPassword: string, fullName?: string): Observable<User> {
    return this.http
      .post<AuthToken>(`${this.baseUrl}/register`, {
        email,
        password,
        confirm_password: confirmPassword,
        full_name: fullName,
      })
      .pipe(
        tap((token) => this.persistToken(token)),
        switchMap(() => this.loadProfile())
      );
  }

  loadProfile(): Observable<User> {
    return this.http.get<User>(`${this.baseUrl}/me`).pipe(
      tap((user) => this.currentUserSubject.next(user))
    );
  }

  logout(): void {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    this.currentUserSubject.next(null);
  }

  private persistToken(token: AuthToken): void {
    localStorage.setItem('token', token.access_token);
    localStorage.setItem('role', token.role);
    localStorage.setItem('user_id', token.user_id.toString());
  }

  private restoreSession(): void {
    if (!this.token) {
      return;
    }
    this.loadProfile().subscribe({
      error: () => {
        this.logout();
      },
    });
  }
}
