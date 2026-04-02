import type { Locale } from './messages';

export const LOCALE_STORAGE_KEY = 'participant_web.locale';

export function detectLocale(): Locale {
  if (typeof window === 'undefined') return 'en';

  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored === 'en' || stored === 'ru') {
    return stored;
  }

  const browserLocale = window.navigator.language.toLowerCase();
  return browserLocale.startsWith('ru') ? 'ru' : 'en';
}

