import { useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { useParticipantFlow } from './hooks/useParticipantFlow';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { BlockQuestionnairePage } from './pages/BlockQuestionnairePage';
import { CompletionPage } from './pages/CompletionPage';
import { ConsentPage } from './pages/ConsentPage';
import { InstructionsPage } from './pages/InstructionsPage';
import { FinalSubmitPage } from './pages/FinalSubmitPage';
import { TrialPage } from './pages/TrialPage';

import './styles.css';

function AppBody() {
  const [consentChecked, setConsentChecked] = useState(false);
  const { t } = useLocale();

  const {
    stage,
    currentTrial,
    questionnaireBlockId,
    progress,
    loading,
    error,
    completionCode,
    runSlug,
    publicRun,
    onboardingReady,
    resumeBannerKey,
    setStage,
    beginSession,
    submitCurrentTrial,
    submitQuestionnaire,
    submitFinalSession,
    retryCurrent,
  } = useParticipantFlow();


  return (
    <main className="app-shell">
      <LanguageSwitcher />
      {error && (
        <section className="card error">
          <p>{error}</p>
          <button type="button" onClick={retryCurrent}>
            {t('error.retry')}
          </button>
        </section>
      )}

      {stage === 'consent' && (
        <ConsentPage
          consentChecked={consentChecked}
          setConsentChecked={setConsentChecked}
          onContinue={() => setStage('instructions')}
        />
      )}

      {stage === 'instructions' && (
        <>
          {!onboardingReady && (
            <section className="card">
              <h1>{t('entry.title')}</h1>
              <p>{t('entry.missingRun')}</p>
              <p className="muted">{t('entry.contactCoordinator')}</p>
            </section>
          )}
          {onboardingReady && (
            <InstructionsPage
              runTitle={publicRun?.public_title ?? t('instructions.defaultRunTitle')}
              runDescription={publicRun?.public_description}
              resumeNotice={resumeBannerKey ? t(resumeBannerKey) : null}
              loading={loading}
              runReady={Boolean(runSlug) && Boolean(publicRun?.launchable)}
              onStart={beginSession}
            />
          )}
        </>
      )}

      {stage === 'trial' && currentTrial && (
        <TrialPage
          trial={currentTrial}
          loading={loading}
          onSubmit={submitCurrentTrial}
        />
      )}

      {stage === 'questionnaire' && questionnaireBlockId && (
        <BlockQuestionnairePage
          blockId={questionnaireBlockId}
          loading={loading}
          onSubmit={submitQuestionnaire}
        />
      )}

      {stage === 'completion' && <CompletionPage completionCode={completionCode} />}
      {stage === 'awaiting_final_submit' && (
        <FinalSubmitPage
          loading={loading}
          onSubmit={submitFinalSession}
          completedTrials={progress.completedTrials}
          totalTrials={progress.totalTrials}
        />
      )}
    </main>
  );
}

export default function App() {
  return (
    <LocaleProvider>
      <AppBody />
    </LocaleProvider>
  );
}
