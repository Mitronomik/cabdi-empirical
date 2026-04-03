import { useLocale } from '../i18n/useLocale';

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();

  return (
    <div aria-label={t('lang.label')} style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
      <button type="button" onClick={() => setLocale('en')} disabled={locale === 'en'}>
        EN
      </button>
      <button type="button" onClick={() => setLocale('ru')} disabled={locale === 'ru'}>
        RU
      </button>
    </div>
  );
}
