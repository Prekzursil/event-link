import { Pipe, PipeTransform } from '@angular/core';
import { TranslationService } from '../services/translation.service';

@Pipe({
  name: 'translate',
  standalone: true,
  pure: false,
})
export class TranslatePipe implements PipeTransform {
  constructor(private readonly i18n: TranslationService) {}

  transform(value: string, params?: Record<string, string | number>): string {
    return this.i18n.translate(value, params);
  }
}
