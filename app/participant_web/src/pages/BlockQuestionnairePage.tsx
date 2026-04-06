import { useState } from 'react';

import { useLocale } from '../i18n/useLocale';

interface Props {
  blockId: string;
  onSubmit: (payload: { burden: number; trust: number; usefulness: number }) => void;
  loading: boolean;
  savedFeedback?: boolean;
}

export function BlockQuestionnairePage({ blockId, onSubmit, loading, savedFeedback }: Props) {
  const { t } = useLocale();
  const [mentalDemand, setMentalDemand] = useState(50);
  const [effort, setEffort] = useState(50);
  const [frustration, setFrustration] = useState(50);
  const [trust, setTrust] = useState(50);
  const [usefulness, setUsefulness] = useState(50);

  return (
    <section className="card">
      <h2>
        {t('questionnaire.title')} ({blockId})
      </h2>
      <p className="muted">
        {t('questionnaire.blockLabel')}: {blockId}
      </p>
      <p>{t('questionnaire.intro')}</p>
      <p>{t('questionnaire.rateItems')}</p>

      <label>
        {t('questionnaire.burdenMental')} ({mentalDemand})
      </label>
      <input type="range" min={0} max={100} value={mentalDemand} onChange={(e) => setMentalDemand(Number(e.target.value))} />

      <label>
        {t('questionnaire.burdenEffort')} ({effort})
      </label>
      <input type="range" min={0} max={100} value={effort} onChange={(e) => setEffort(Number(e.target.value))} />

      <label>
        {t('questionnaire.burdenFrustration')} ({frustration})
      </label>
      <input type="range" min={0} max={100} value={frustration} onChange={(e) => setFrustration(Number(e.target.value))} />

      <label>
        {t('questionnaire.trust')} ({trust})
      </label>
      <input type="range" min={0} max={100} value={trust} onChange={(e) => setTrust(Number(e.target.value))} />

      <label>
        {t('questionnaire.usefulness')} ({usefulness})
      </label>
      <input type="range" min={0} max={100} value={usefulness} onChange={(e) => setUsefulness(Number(e.target.value))} />

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
      {savedFeedback ? <p className="muted">{t('common.progressSaved')}</p> : null}
    </section>
  );
}
