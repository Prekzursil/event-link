import RO_STRINGS from './strings.ro.json';
import EN_STRINGS from './strings.en.json';

export { EN_STRINGS, RO_STRINGS };

export const UI_STRINGS = {
  ro: RO_STRINGS,
  en: EN_STRINGS,
} as const;

export type UiStrings = (typeof UI_STRINGS)['ro'];
