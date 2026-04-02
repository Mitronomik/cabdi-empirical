import { useLocale } from '../i18n/useLocale';

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();

  return (
    <div className="language-switcher" aria-label="language switcher">
      <button
        type="button"
        className={locale === 'en' ? 'active' : ''}
        onClick={() => setLocale('en')}
      >
        {t('lang.en')}
      </button>
      <span>|</span>
      <button
        type="button"
        className={locale === 'ru' ? 'active' : ''}
        onClick={() => setLocale('ru')}
      >
        {t('lang.ru')}
      </button>
    </div>
  );
}

