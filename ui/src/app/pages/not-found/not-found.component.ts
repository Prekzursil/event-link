import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="card empty-state">
      <h1>404 - Pagina nu a fost găsită</h1>
      <p>Se pare că linkul nu există sau a fost mutat.</p>
      <a routerLink="/" class="btn ghost">Înapoi la evenimente</a>
    </section>
  `,
})
export class NotFoundComponent {}
