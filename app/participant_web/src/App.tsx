import { useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { useParticipantFlow } from './hooks/useParticipantFlow';
import type { ParticipantStage } from './hooks/participantFlowState';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { BlockQuestionnairePage } from './pages/BlockQuestionnairePage';
import { CompletionPage } from './pages/CompletionPage';
import { ConsentPage } from './pages/ConsentPage';
import { InstructionsPage } from './pages/InstructionsPage';
import { FinalSubmitPage } from './pages/FinalSubmitPage';
import { TrialPage } from './pages/TrialPage';

import './styles.css';

function ResumePromptCard({
  loading,
  onContinue,
  onRestart,
}: {
  loading: boolean;
  onContinue: () => void;
  onRestart: () => void;
}) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('instructions.title')}</h1>
      <p>{t('entry.resumeResumed')}</p>
      <div className="button-row">
        <button type="button" disabled={loading} onClick={onContinue}>
          {t('common.continue')}
        </button>
        <button type="button" disabled={loading} onClick={onRestart}>
          {t('instructions.startPractice')}
        </button>
      </div>
    </section>
  );
}

function AppBody() {
  const [consentChecked, setConsentChecked] = useState(false);
  const { t } = useLocale();

  const flow = useParticipantFlow();

  const stageContentByKey: Partial<Record<ParticipantStage, JSX.Element | null>> = {
    consent: (
      <ConsentPage
        consentChecked={consentChecked}
        setConsentChecked={setConsentChecked}
        onContinue={() => flow.setStage('instructions')}
      />
    ),
    instructions: !flow.onboardingReady ? (
      <section className="card">
        <h1>{t('entry.title')}</h1>
        <p>{t('entry.missingRun')}</p>
        <p className="muted">{t('entry.contactCoordinator')}</p>
      </section>
    ) : (
      <InstructionsPage
        runTitle={flow.publicRun?.public_title ?? t('instructions.defaultRunTitle')}
        runDescription={flow.publicRun?.public_description}
        resumeNotice={flow.resumeBannerKey ? t(flow.resumeBannerKey) : null}
        loading={flow.loading}
        runReady={Boolean(flow.runSlug) && Boolean(flow.publicRun?.launchable)}
        onStart={flow.beginSession}
      />
    ),
    resume_prompt: (
      <ResumePromptCard
        loading={flow.loading}
        onContinue={flow.continueResumedSession}
        onRestart={() => flow.setStage('consent')}
      />
    ),
    trial: flow.currentTrial ? (
      <TrialPage
        trial={flow.currentTrial}
        loading={flow.loading}
        savedFeedback={flow.savedFeedback}
        onSubmit={flow.submitCurrentTrial}
      />
    ) : null,
    questionnaire: flow.questionnaireBlockId ? (
      <BlockQuestionnairePage
        blockId={flow.questionnaireBlockId}
        loading={flow.loading}
        savedFeedback={flow.savedFeedback}
        onSubmit={flow.submitQuestionnaire}
      />
    ) : null,
    awaiting_final_submit: (
      <FinalSubmitPage
        loading={flow.loading}
        onSubmit={flow.submitFinalSession}
        completedTrials={flow.progress.completedTrials}
        totalTrials={flow.progress.totalTrials}
      />
    ),
    completion: <CompletionPage completionCode={flow.completionCode} />,
  };

  return (
    <main className="app-shell">
      <LanguageSwitcher />
      {flow.error && (
        <section className="card error">
          <p>{flow.error}</p>
          <button type="button" onClick={flow.retryCurrent}>
            {t('error.retry')}
          </button>
        </section>
      )}

      {stageContentByKey[flow.stage] ?? null}
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
