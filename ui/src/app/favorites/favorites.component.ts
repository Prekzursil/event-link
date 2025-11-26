import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EventItem } from '../models';
import { EventService } from '../services/event.service';
import { TranslatePipe } from '../pipes/translate.pipe';

@Component({
  selector: 'app-favorites',
  standalone: true,
  imports: [CommonModule, RouterLink, TranslatePipe],
  templateUrl: './favorites.component.html',
  styleUrl: './favorites.component.scss',
})
export class FavoritesComponent implements OnInit {
  items: EventItem[] = [];
  loading = true;
  error = '';

  constructor(private eventService: EventService) {}

  ngOnInit(): void {
    this.eventService.favorites().subscribe({
      next: (res) => {
        this.items = res.items;
        this.loading = false;
      },
      error: () => {
        this.error = 'Nu am putut încărca favoritele.';
        this.loading = false;
      },
    });
  }
}
