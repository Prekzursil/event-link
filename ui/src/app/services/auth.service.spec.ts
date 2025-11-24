import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AuthService } from './auth.service';
import { API_BASE_URL } from '../api-tokens';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        AuthService,
        { provide: API_BASE_URL, useValue: 'http://test-api' },
      ],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
    localStorage.clear();
  });

  it('should login and store token', () => {
    service.login('test@test.com', 'pass').subscribe();
    const req = httpMock.expectOne('http://test-api/login');
    req.flush({ access_token: 'abc', token_type: 'bearer', role: 'student', user_id: 1 });
    expect(localStorage.getItem('token')).toBe('abc');
  });

  it('should logout and clear token', () => {
    localStorage.setItem('token', 'abc');
    service.logout();
    expect(localStorage.getItem('token')).toBeNull();
  });
});
