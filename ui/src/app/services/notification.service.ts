import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastMessage {
  id: number;
  type: ToastType;
  text: string;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private messages$ = new BehaviorSubject<ToastMessage[]>([]);
  private counter = 0;

  stream() {
    return this.messages$.asObservable();
  }

  success(text: string) {
    this.push(text, 'success');
  }

  error(text: string) {
    this.push(text, 'error');
  }

  info(text: string) {
    this.push(text, 'info');
  }

  dismiss(id: number) {
    this.messages$.next(this.messages$.value.filter((m) => m.id !== id));
  }

  private push(text: string, type: ToastType) {
    const toast: ToastMessage = { id: ++this.counter, type, text };
    this.messages$.next([...this.messages$.value, toast]);
    setTimeout(() => this.dismiss(toast.id), 5000);
  }
}
