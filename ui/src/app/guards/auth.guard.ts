import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isLoggedIn()) {
    return router.createUrlTree(['/login'], { queryParams: { redirect: state.url } });
  }

  const requiredRole = route.data?.['role'] as string | undefined;
  if (requiredRole && auth.role !== requiredRole) {
    return router.createUrlTree(['/']);
  }

  return true;
};
