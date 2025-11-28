import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { organizerGuard } from './organizer.guard';
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

describe('organizerGuard', () => {
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

  it('redirects unauthenticated to login', () => {
    const tree = TestBed.runInInjectionContext(() => organizerGuard({} as any, {} as any));
    expect(tree instanceof UrlTree).toBeTrue();
    expect((tree as UrlTree).toString()).toContain('/login');
  });

  it('redirects non-organizer to forbidden', () => {
    auth.loggedIn = true;
    auth.role = 'student';
    const tree = TestBed.runInInjectionContext(() => organizerGuard({} as any, {} as any));
    expect(tree instanceof UrlTree).toBeTrue();
    expect((tree as UrlTree).toString()).toBe('/forbidden');
  });

  it('allows organizers', () => {
    auth.loggedIn = true;
    auth.role = 'organizator';
    const result = TestBed.runInInjectionContext(() => organizerGuard({} as any, {} as any));
    expect(result).toBeTrue();
  });
});
