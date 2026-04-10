import { useEffect, useRef, useState } from 'react';

import { useLocale } from '../i18n/useLocale';

interface Props {
  blockId: string;
  onSubmit: (payload: { burden: number; trust: number; usefulness: number }) => void;
  loading: boolean;
  savedFeedback?: boolean;
}

interface QuestionnaireDraft {
  mentalDemand: number;
  effort: number;
  frustration: number;
  trust: number;
  usefulness: number;
}

function questionnaireDraftKey(blockId: string): string {
  return `participant_web.questionnaire_draft.${blockId}`;
}

export function BlockQuestionnairePage({ blockId, onSubmit, loading, savedFeedback }: Props) {
  const { t } = useLocale();
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const [mentalDemand, setMentalDemand] = useState(50);
  const [effort, setEffort] = useState(50);
  const [frustration, setFrustration] = useState(50);
  const [trust, setTrust] = useState(50);
  const [usefulness, setUsefulness] = useState(50);

  useEffect(() => {
    headingRef.current?.focus();
    const raw = window.sessionStorage.getItem(questionnaireDraftKey(blockId));
    if (!raw) return;
    try {
      const draft = JSON.parse(raw) as Partial<QuestionnaireDraft>;
      if (typeof draft.mentalDemand === 'number') setMentalDemand(draft.mentalDemand);
      if (typeof draft.effort === 'number') setEffort(draft.effort);
      if (typeof draft.frustration === 'number') setFrustration(draft.frustration);
      if (typeof draft.trust === 'number') setTrust(draft.trust);
      if (typeof draft.usefulness === 'number') setUsefulness(draft.usefulness);
    } catch {
      window.sessionStorage.removeItem(questionnaireDraftKey(blockId));
    }
  }, [blockId]);

  useEffect(() => {
    window.sessionStorage.setItem(
      questionnaireDraftKey(blockId),
      JSON.stringify({ mentalDemand, effort, frustration, trust, usefulness } satisfies QuestionnaireDraft),
    );
  }, [blockId, mentalDemand, effort, frustration, trust, usefulness]);

  return (
    <section className="card">
      <h2 ref={headingRef} tabIndex={-1} className="focus-anchor">
        {t('questionnaire.title')} ({blockId})
      </h2>
      <p className="muted">
        {t('questionnaire.blockLabel')}: {blockId}
      </p>
      <p>{t('questionnaire.intro')}</p>
      <p>{t('questionnaire.rateItems')}</p>

      <label htmlFor="q-mental">{t('questionnaire.burdenMental')} ({mentalDemand})</label>
      <input id="q-mental" type="range" min={0} max={100} value={mentalDemand} onChange={(e) => setMentalDemand(Number(e.target.value))} />

      <label htmlFor="q-effort">{t('questionnaire.burdenEffort')} ({effort})</label>
      <input id="q-effort" type="range" min={0} max={100} value={effort} onChange={(e) => setEffort(Number(e.target.value))} />

      <label htmlFor="q-frustration">{t('questionnaire.burdenFrustration')} ({frustration})</label>
      <input id="q-frustration" type="range" min={0} max={100} value={frustration} onChange={(e) => setFrustration(Number(e.target.value))} />

      <label htmlFor="q-trust">{t('questionnaire.trust')} ({trust})</label>
      <input id="q-trust" type="range" min={0} max={100} value={trust} onChange={(e) => setTrust(Number(e.target.value))} />

      <label htmlFor="q-usefulness">{t('questionnaire.usefulness')} ({usefulness})</label>
      <input id="q-usefulness" type="range" min={0} max={100} value={usefulness} onChange={(e) => setUsefulness(Number(e.target.value))} />

      <button
        type="button"
        disabled={loading}
        onClick={() =>
          onSubmit({
            burden: Math.round((mentalDemand + effort + frustration) / 3),
            trust,
            usefulness,
          })
        }
      >
        {t('questionnaire.submit')}
      </button>
      <div aria-live="polite">{savedFeedback ? <p className="muted">{t('common.progressSaved')}</p> : null}</div>
    </section>
  );
}
