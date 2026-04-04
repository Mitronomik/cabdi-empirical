import { useLocale } from '../i18n/useLocale';

interface Props {
  loading: boolean;
  onSubmit: () => void;
}

export function FinalSubmitPage({ loading, onSubmit }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('finalSubmit.title')}</h1>
      <p>{t('finalSubmit.ready')}</p>
      <p>{t('finalSubmit.note')}</p>
      <button type="button" onClick={onSubmit} disabled={loading}>
        {loading ? t('finalSubmit.submitting') : t('finalSubmit.button')}
      </button>
    </section>
  );
}
