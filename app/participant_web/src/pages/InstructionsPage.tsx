import { useLocale } from '../i18n/useLocale';

interface Props {
  runSlug: string;
  setRunSlug: (value: string) => void;
  onStart: () => void;
  loading: boolean;
}

export function InstructionsPage({ runSlug, setRunSlug, onStart, loading }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('instructions.title')}</h1>
      <ul>
        <li>{t('instructions.item.classify')}</li>
        <li>{t('instructions.item.assistance')}</li>
        <li>{t('instructions.item.aiWrong')}</li>
        <li>{t('instructions.item.noBlindFollow')}</li>
        <li>{t('instructions.item.practice')}</li>
      </ul>
      <label htmlFor="run-slug">{t('instructions.runSlugLabel')}</label>
      <input
        id="run-slug"
        value={runSlug}
        onChange={(e) => setRunSlug(e.target.value)}
        placeholder={t('instructions.runSlugPlaceholder')}
      />
      <button type="button" disabled={!runSlug || loading} onClick={onStart}>
        {t('instructions.startPractice')}
      </button>
    </section>
  );
}
