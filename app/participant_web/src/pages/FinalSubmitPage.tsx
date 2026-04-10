import { useEffect, useRef, useState } from 'react';

import { useLocale } from '../i18n/useLocale';

interface Props {
  loading: boolean;
  onSubmit: () => void;
  completedTrials: number;
  totalTrials: number;
}

export function FinalSubmitPage({ loading, onSubmit, completedTrials, totalTrials }: Props) {
  const { t } = useLocale();
  const [confirmed, setConfirmed] = useState(false);
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <section className="card">
      <h1 ref={headingRef} tabIndex={-1} className="focus-anchor">{t('finalSubmit.title')}</h1>
      <p>{t('finalSubmit.ready')}</p>
      <p>
        {t('finalSubmit.progress')}: {completedTrials} / {totalTrials}
      </p>
      <p>{t('finalSubmit.note')}</p>
      <p className="muted">{t('finalSubmit.resumeUntilSubmit')}</p>
      <label className="verification-check">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        {t('finalSubmit.confirmation')}
      </label>
      <button type="button" onClick={onSubmit} disabled={loading || !confirmed}>
        {loading ? t('finalSubmit.submitting') : t('finalSubmit.button')}
      </button>
    </section>
  );
}
