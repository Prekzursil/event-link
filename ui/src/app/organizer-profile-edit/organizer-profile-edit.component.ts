import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { OrganizerProfile } from '../models';
import { EventService } from '../services/event.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-organizer-profile-edit',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './organizer-profile-edit.component.html',
  styleUrl: './organizer-profile-edit.component.scss',
})
export class OrganizerProfileEditComponent implements OnInit {
  profile: Partial<OrganizerProfile> = {};
  loading = true;
  error = '';
  saving = false;

  constructor(private eventService: EventService, private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    const userId = this.auth.userId();
    if (!userId) {
      this.error = 'Autentifică-te.';
      this.loading = false;
      return;
    }
    this.eventService.organizerProfile(userId).subscribe({
      next: (profile) => {
        this.profile = profile;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  save(): void {
    this.saving = true;
    this.eventService.updateOrganizerProfile(this.profile).subscribe({
      next: (res) => {
        this.profile = res;
        this.saving = false;
        this.router.navigate(['/organizers', res.user_id]);
      },
      error: () => {
        this.error = 'Nu am putut salva profilul.';
        this.saving = false;
      },
    });
  }
}
