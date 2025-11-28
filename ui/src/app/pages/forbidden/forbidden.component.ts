import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-forbidden',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="card empty-state">
      <h1>403 - Acces interzis</h1>
      <p>Nu ai permisiunea de a accesa această pagină.</p>
      <a routerLink="/" class="btn ghost">Înapoi la evenimente</a>
    </section>
  `,
})
export class ForbiddenComponent {}
