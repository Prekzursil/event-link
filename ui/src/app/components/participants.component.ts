import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { EventService } from '../services/event.service';

@Component({
  selector: 'app-participants',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h2>Participanți</h2>
    <div *ngIf="!participants.length">Nu există înscrieri încă.</div>
    <div>{{ participants.length }} / {{ maxSeats || '∞' }} înscriși</div>
    <ul>
      <li *ngFor="let p of participants">{{ p.email }}</li>
    </ul>
  `,
})
export class ParticipantsComponent implements OnInit {
  participants: any[] = [];
  maxSeats?: number;

  constructor(private route: ActivatedRoute, private eventsApi: EventService) {}

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.eventsApi.participants(id).subscribe((res) => {
      this.participants = res.participants;
      this.maxSeats = res.max_seats;
    });
  }
}
