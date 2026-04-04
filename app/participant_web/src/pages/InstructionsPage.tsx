import { useLocale } from '../i18n/useLocale';

interface Props {
  runTitle: string;
  runDescription?: string | null;
  loading: boolean;
  runReady: boolean;
  onStart: () => void;
}

export function InstructionsPage({ runTitle, runDescription, loading, runReady, onStart }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('instructions.title')}</h1>
      <p className="muted">{runTitle}</p>
      {runDescription ? <p>{runDescription}</p> : null}
      <ul>
        <li>{t('instructions.item.classify')}</li>
        <li>{t('instructions.item.assistance')}</li>
        <li>{t('instructions.item.aiWrong')}</li>
        <li>{t('instructions.item.noBlindFollow')}</li>
        <li>{t('instructions.item.practice')}</li>
      </ul>
      <p className="reassurance">{t('instructions.resumeHint')}</p>
      <button type="button" disabled={!runReady || loading} onClick={onStart}>
        {loading ? t('instructions.starting') : t('instructions.startPractice')}
      </button>
    </section>
  );
}
