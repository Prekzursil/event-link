import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { publicOnlyGuard } from './public-only.guard';
import { AuthService } from '../services/auth.service';

class AuthStub {
  loggedIn = false;
  isLoggedIn() {
    return this.loggedIn;
  }
}

describe('publicOnlyGuard', () => {
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

  it('allows navigation when not logged in', () => {
    const result = TestBed.runInInjectionContext(() => publicOnlyGuard({} as any, { url: '/login' } as any));
    expect(result).toBeTrue();
  });

  it('redirects logged-in users to home', () => {
    auth.loggedIn = true;
    const result = TestBed.runInInjectionContext(() => publicOnlyGuard({} as any, { url: '/login' } as any));
    expect(result instanceof UrlTree).toBeTrue();
    expect((result as UrlTree).toString()).toBe('/');
  });
});
