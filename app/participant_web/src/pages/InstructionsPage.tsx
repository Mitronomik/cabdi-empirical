import { useLocale } from '../i18n/useLocale';

interface Props {
  participantId: string;
  setParticipantId: (value: string) => void;
  runSlug: string;
  setRunSlug: (value: string) => void;
  onStart: () => void;
  loading: boolean;
}

export function InstructionsPage({ participantId, setParticipantId, runSlug, setRunSlug, onStart, loading }: Props) {
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
      <label htmlFor="participant-id">{t('instructions.participantIdLabel')}</label>
      <input
        id="participant-id"
        value={participantId}
        onChange={(e) => setParticipantId(e.target.value)}
        placeholder={t('instructions.participantIdPlaceholder')}
      />
      <label htmlFor="run-slug">{t('instructions.runSlugLabel')}</label>
      <input
        id="run-slug"
        value={runSlug}
        onChange={(e) => setRunSlug(e.target.value)}
        placeholder={t('instructions.runSlugPlaceholder')}
      />
      <button type="button" disabled={!participantId || !runSlug || loading} onClick={onStart}>
        {t('instructions.startPractice')}
      </button>
    </section>
  );
}
