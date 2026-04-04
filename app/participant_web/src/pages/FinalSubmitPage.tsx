import { useLocale } from '../i18n/useLocale';

interface Props {
  loading: boolean;
  onSubmit: () => void;
  completedTrials: number;
  totalTrials: number;
}

export function FinalSubmitPage({ loading, onSubmit, completedTrials, totalTrials }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('finalSubmit.title')}</h1>
      <p>{t('finalSubmit.ready')}</p>
      <p>
        {t('finalSubmit.progress')}: {completedTrials} / {totalTrials}
      </p>
      <p>{t('finalSubmit.note')}</p>
      <p className="muted">{t('finalSubmit.resumeUntilSubmit')}</p>
      <button type="button" onClick={onSubmit} disabled={loading}>
        {loading ? t('finalSubmit.submitting') : t('finalSubmit.button')}
      </button>
    </section>
  );
}
