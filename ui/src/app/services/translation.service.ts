import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { SupportedLang, translations } from '../i18n';

@Injectable({ providedIn: 'root' })
export class TranslationService {
  private lang$ = new BehaviorSubject<SupportedLang>('ro');

  setLang(lang: SupportedLang): void {
    this.lang$.next(lang);
  }

  toggle(): void {
    this.setLang(this.getLang() === 'ro' ? 'en' : 'ro');
  }

  getLang(): SupportedLang {
    return this.lang$.getValue();
  }

  translate(key: string, params?: Record<string, string | number>): string {
    const lang = this.getLang();
    const catalog = translations[lang] || {};
    let value = catalog[key] || translations.ro[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        value = value.replace(`{{${k}}}`, String(v));
      });
    }
    return value;
  }
}
