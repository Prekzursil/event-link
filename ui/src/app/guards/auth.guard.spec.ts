import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { authGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';

class AuthStub {
  loggedIn = false;
  role: string | null = null;
  isLoggedIn() {
    return this.loggedIn;
  }
  isOrganizer() {
    return this.role === 'organizator';
  }
}

describe('authGuard', () => {
  let router: Router;
  let auth: AuthStub;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [RouterTestingModule.withRoutes([])],
      providers: [{ provide: AuthService, useClass: AuthStub }],
    });
    router = TestBed.inject(Router);
    auth = TestBed.inject(AuthService) as unknown as AuthStub;
  });

  it('redirects unauthenticated users to login with redirect param', () => {
    const tree = TestBed.runInInjectionContext(() => authGuard({ data: {} } as any, { url: '/protected' } as any));
    expect(tree instanceof UrlTree).toBeTrue();
    expect((tree as UrlTree).toString()).toContain('/login');
    expect((tree as UrlTree).queryParams['redirect']).toBe('/protected');
  });

  it('redirects wrong role users to home', () => {
    auth.loggedIn = true;
    auth.role = 'student';
    const tree = TestBed.runInInjectionContext(() => authGuard({ data: { role: 'organizator' } } as any, { url: '/org' } as any));
    expect(tree instanceof UrlTree).toBeTrue();
    expect((tree as UrlTree).toString()).toBe('/');
  });

  it('allows access when role matches', () => {
    auth.loggedIn = true;
    auth.role = 'student';
    const result = TestBed.runInInjectionContext(() => authGuard({ data: { role: 'student' } } as any, { url: '/s' } as any));
    expect(result).toBeTrue();
  });
});
