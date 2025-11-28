import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { NotificationService, ToastMessage } from '../services/notification.service';

@Component({
  selector: 'app-notifications',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './notifications.component.html',
  styleUrl: './notifications.component.scss',
})
export class NotificationsComponent implements OnInit, OnDestroy {
  messages: ToastMessage[] = [];
  private sub?: Subscription;

  constructor(private notifications: NotificationService) {}

  ngOnInit(): void {
    this.sub = this.notifications.stream().subscribe((msgs) => (this.messages = msgs));
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  dismiss(id: number): void {
    this.notifications.dismiss(id);
  }
}
