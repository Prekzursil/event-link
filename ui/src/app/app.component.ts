import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from './services/auth.service';
import { TranslationService } from './services/translation.service';
import { TranslatePipe } from './pipes/translate.pipe';
import { NotificationsComponent } from './notifications/notifications.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, TranslatePipe, NotificationsComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  title = 'Event Link';
  showMobileMenu = false;

  constructor(public auth: AuthService, private router: Router, public i18n: TranslationService) {}

  logout() {
    this.auth.logout();
    this.router.navigate(['/']);
  }

  toggleMenu(): void {
    this.showMobileMenu = !this.showMobileMenu;
  }

  closeMenu(): void {
    this.showMobileMenu = false;
  }

  toggleLang(): void {
    this.i18n.toggle();
  }
}
