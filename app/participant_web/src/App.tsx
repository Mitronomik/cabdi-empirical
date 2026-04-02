import { useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { useParticipantFlow } from './hooks/useParticipantFlow';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { BlockQuestionnairePage } from './pages/BlockQuestionnairePage';
import { CompletionPage } from './pages/CompletionPage';
import { ConsentPage } from './pages/ConsentPage';
import { InstructionsPage } from './pages/InstructionsPage';
import { TrialPage } from './pages/TrialPage';

import './styles.css';

function AppBody() {
  const [consentChecked, setConsentChecked] = useState(false);
  const [participantId, setParticipantId] = useState('p_001');
  const { t } = useLocale();

  const {
    stage,
    currentTrial,
    questionnaireBlockId,
    progress,
    loading,
    error,
    completionCode,
    setStage,
    beginSession,
    submitCurrentTrial,
    submitQuestionnaire,
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
        <InstructionsPage
          participantId={participantId}
          setParticipantId={setParticipantId}
          loading={loading}
          onStart={() => beginSession(participantId)}
        />
      )}

      {stage === 'trial' && currentTrial && (
        <TrialPage
          trial={currentTrial}
          loading={loading}
          completedTrials={progress.completedTrials}
          totalTrials={progress.totalTrials}
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
