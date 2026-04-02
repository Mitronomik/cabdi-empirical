import { useLocale } from '../i18n/useLocale';

interface Props {
  consentChecked: boolean;
  setConsentChecked: (value: boolean) => void;
  onContinue: () => void;
}

export function ConsentPage({ consentChecked, setConsentChecked, onContinue }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('consent.title')}</h1>
      <p>{t('consent.description')}</p>
      <label>
        <input
          type="checkbox"
          checked={consentChecked}
          onChange={(e) => setConsentChecked(e.target.checked)}
        />
        {t('consent.checkbox')}
      </label>
      <button type="button" disabled={!consentChecked} onClick={onContinue}>
        {t('common.continue')}
      </button>
    </section>
  );
}
