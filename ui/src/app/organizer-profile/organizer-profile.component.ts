import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { EventService } from '../services/event.service';
import { OrganizerProfile } from '../models';
import { TranslatePipe } from '../pipes/translate.pipe';

@Component({
  selector: 'app-organizer-profile',
  standalone: true,
  imports: [CommonModule, RouterLink, TranslatePipe],
  templateUrl: './organizer-profile.component.html',
  styleUrl: './organizer-profile.component.scss',
})
export class OrganizerProfileComponent implements OnInit {
  profile?: OrganizerProfile;
  loading = true;
  error = '';
  placeholderLogo = '/assets/cover-placeholder.svg';

  constructor(private route: ActivatedRoute, private eventService: EventService) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (id) {
      this.eventService.organizerProfile(id).subscribe({
        next: (profile) => {
          this.profile = profile;
          this.loading = false;
        },
        error: () => {
          this.error = 'Organizatorul nu a fost găsit.';
          this.loading = false;
        },
      });
    } else {
      this.error = 'Organizatorul nu a fost găsit.';
      this.loading = false;
    }
  }
}
