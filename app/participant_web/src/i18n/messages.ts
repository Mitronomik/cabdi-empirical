export const SUPPORTED_LOCALES = ['en', 'ru'] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export type MessageKey =
  | 'lang.en'
  | 'lang.ru'
  | 'lang.switcherLabel'
  | 'trial.progressAria'
  | 'assistance.panelAria'
  | 'error.runSlugRequired'
  | 'error.retry'
  | 'error.loadNextTrial'
  | 'error.startSession'
  | 'error.missingSessionState'
  | 'error.submitTrial'
  | 'error.missingQuestionnaireState'
  | 'error.submitQuestionnaire'
  | 'error.missingSessionStateShort'
  | 'error.finalSubmit'
  | 'consent.title'
  | 'consent.description'
  | 'consent.checkbox'
  | 'common.continue'
  | 'instructions.title'
  | 'instructions.item.classify'
  | 'instructions.item.assistance'
  | 'instructions.item.aiWrong'
  | 'instructions.item.noBlindFollow'
  | 'instructions.item.practice'
  | 'instructions.runSlugLabel'
  | 'instructions.runSlugPlaceholder'
  | 'instructions.startPractice'
  | 'trial.progressLabel'
  | 'trial.caseTitle'
  | 'trial.noPrompt'
  | 'trial.blockLabel'
  | 'trial.decisionTitle'
  | 'trial.selfConfidence'
  | 'trial.submit'
  | 'assistance.title'
  | 'assistance.prediction'
  | 'assistance.modelConfidence'
  | 'assistance.rationale'
  | 'assistance.defaultRationale'
  | 'assistance.defaultEvidence'
  | 'assistance.showRationale'
  | 'assistance.showEvidence'
  | 'assistance.hideEvidence'
  | 'assistance.verifyHint'
  | 'assistance.forcedCheckbox'
  | 'assistance.secondLook'
  | 'questionnaire.title'
  | 'questionnaire.rateItems'
  | 'questionnaire.burdenMental'
  | 'questionnaire.burdenEffort'
  | 'questionnaire.burdenFrustration'
  | 'questionnaire.trust'
  | 'questionnaire.usefulness'
  | 'questionnaire.submit'
  | 'finalSubmit.title'
  | 'finalSubmit.ready'
  | 'finalSubmit.note'
  | 'finalSubmit.button'
  | 'finalSubmit.submitting'
  | 'completion.title'
  | 'completion.thanks'
  | 'completion.done'
  | 'completion.code';

export const messages: Record<Locale, Record<MessageKey, string>> = {
  en: {
    'lang.en': 'EN',
    'lang.ru': 'RU',
    'lang.switcherLabel': 'Language switcher',
    'trial.progressAria': 'progress',
    'assistance.panelAria': 'AI assistance panel',
    'error.runSlugRequired': 'Run slug is required.',
    'error.retry': 'Retry',
    'error.loadNextTrial': 'Could not load the next trial. Please retry.',
    'error.startSession': 'Unable to start session. Please retry.',
    'error.missingSessionState': 'Missing session state. Please restart this participant run.',
    'error.submitTrial': 'Could not submit trial. Please retry submit.',
    'error.missingQuestionnaireState':
      'Missing session state for questionnaire. Please restart this participant run.',
    'error.submitQuestionnaire': 'Could not submit questionnaire. Please retry.',
    'error.missingSessionStateShort': 'Missing session state.',
    'error.finalSubmit': 'Could not finalize session. Please retry final submit.',
    'consent.title': 'Consent',
    'consent.description':
      'This is a research task. Your responses will be recorded for pilot research purposes.',
    'consent.checkbox': 'I consent to participate in this research task.',
    'common.continue': 'Continue',
    'instructions.title': 'Instructions',
    'instructions.item.classify': 'You will classify cases as part of a research task.',
    'instructions.item.assistance': 'AI assistance may be shown during some trials.',
    'instructions.item.aiWrong': 'The AI can be wrong.',
    'instructions.item.noBlindFollow': 'Do not blindly follow the AI recommendation.',
    'instructions.item.practice': 'You will complete practice trials before the main blocks.',
    'instructions.runSlugLabel': 'Run link slug',
    'instructions.runSlugPlaceholder': 'e.g., spring-2026-cohort-a',
    'instructions.startPractice': 'Start practice',
    'trial.progressLabel': 'Trial',
    'trial.caseTitle': 'Case',
    'trial.noPrompt': 'No prompt provided.',
    'trial.blockLabel': 'Block',
    'trial.decisionTitle': 'Your decision',
    'trial.selfConfidence': 'Self-confidence',
    'trial.submit': 'Submit trial',
    'assistance.title': 'AI Assistance',
    'assistance.prediction': 'Prediction',
    'assistance.modelConfidence': 'Model confidence',
    'assistance.rationale': 'Rationale',
    'assistance.defaultRationale': 'Model reasoning summary unavailable.',
    'assistance.defaultEvidence': 'Evidence snippets are not available for this item.',
    'assistance.showRationale': 'Show rationale',
    'assistance.showEvidence': 'Show evidence',
    'assistance.hideEvidence': 'Hide evidence',
    'assistance.verifyHint': 'Reminder: the AI can be wrong. Verify before submitting.',
    'assistance.forcedCheckbox': 'I reviewed the AI output and made an independent judgment.',
    'assistance.secondLook': 'Mark second look complete',
    'questionnaire.title': 'Block questionnaire',
    'questionnaire.rateItems': 'Rate each item from 0 to 100.',
    'questionnaire.burdenMental': 'Burden: mental demand',
    'questionnaire.burdenEffort': 'Burden: effort',
    'questionnaire.burdenFrustration': 'Burden: frustration',
    'questionnaire.trust': 'Trust / reliance',
    'questionnaire.usefulness': 'Usefulness',
    'questionnaire.submit': 'Submit questionnaire',
    'finalSubmit.title': 'Final submit required',
    'finalSubmit.ready': 'All required trials and questionnaires are complete.',
    'finalSubmit.note': 'Use final submit to finalize your session and unlock completion.',
    'finalSubmit.button': 'Final submit',
    'finalSubmit.submitting': 'Submitting...',
    'completion.title': 'Complete',
    'completion.thanks': 'Thank you for participating in this pilot research task.',
    'completion.done': 'Your session is complete.',
    'completion.code': 'Completion code',
  },
  ru: {
    'lang.en': 'EN',
    'lang.ru': 'RU',

    'lang.switcherLabel': 'Переключатель языка',
    'trial.progressAria': 'прогресс',
    'assistance.panelAria': 'Панель помощи ИИ',
    'error.runSlugRequired': 'Требуется slug запуска.',
    'error.retry': 'Повторить',
    'error.loadNextTrial': 'Не удалось загрузить следующий раунд. Пожалуйста, попробуйте снова.',
    'error.startSession': 'Не удалось начать сессию. Пожалуйста, попробуйте снова.',
    'error.missingSessionState': 'Состояние сессии отсутствует. Пожалуйста, перезапустите участие.',
    'error.submitTrial': 'Не удалось отправить ответ. Пожалуйста, повторите отправку.',
    'error.missingQuestionnaireState':
      'Состояние сессии для анкеты отсутствует. Пожалуйста, перезапустите участие.',
    'error.submitQuestionnaire': 'Не удалось отправить анкету. Пожалуйста, попробуйте снова.',
    'error.missingSessionStateShort': 'Состояние сессии отсутствует.',
    'error.finalSubmit': 'Не удалось завершить сессию. Пожалуйста, повторите финальную отправку.',
    'consent.title': 'Согласие',
    'consent.description':
      'Это исследовательское задание. Ваши ответы будут записаны для пилотного исследования.',
    'consent.checkbox': 'Я согласен(на) участвовать в этом исследовательском задании.',
    'common.continue': 'Продолжить',
    'instructions.title': 'Инструкция',
    'instructions.item.classify': 'Вам предстоит классифицировать кейсы в рамках исследовательской задачи.',
    'instructions.item.assistance': 'В некоторых раундах может показываться помощь ИИ.',
    'instructions.item.aiWrong': 'ИИ может ошибаться.',
    'instructions.item.noBlindFollow': 'Не следуйте рекомендации ИИ вслепую.',
    'instructions.item.practice':
      'Перед основными блоками вы пройдёте тренировочные раунды.',
    'instructions.runSlugLabel': 'Публичный slug запуска',
    'instructions.runSlugPlaceholder': 'например, spring-2026-cohort-a',
    'instructions.startPractice': 'Начать тренировку',
    'trial.progressLabel': 'Раунд',
    'trial.caseTitle': 'Кейс',
    'trial.noPrompt': 'Текст задания не предоставлен.',
    'trial.blockLabel': 'Блок',
    'trial.decisionTitle': 'Ваше решение',
    'trial.selfConfidence': 'Уверенность в ответе',
    'trial.submit': 'Отправить ответ',
    'assistance.title': 'Помощь ИИ',
    'assistance.prediction': 'Прогноз',
    'assistance.modelConfidence': 'Уверенность модели',
    'assistance.rationale': 'Обоснование',
    'assistance.defaultRationale': 'Краткое обоснование модели недоступно.',
    'assistance.defaultEvidence': 'Фрагменты доказательств для этого кейса недоступны.',
    'assistance.showRationale': 'Показать обоснование',
    'assistance.showEvidence': 'Показать доказательства',
    'assistance.hideEvidence': 'Скрыть доказательства',
    'assistance.verifyHint': 'Напоминание: ИИ может ошибаться. Проверьте ответ перед отправкой.',
    'assistance.forcedCheckbox':
      'Я проверил(а) вывод ИИ и принял(а) независимое решение.',
    'assistance.secondLook': 'Отметить повторную проверку',
    'questionnaire.title': 'Анкета по блоку',
    'questionnaire.rateItems': 'Оцените каждый пункт от 0 до 100.',
    'questionnaire.burdenMental': 'Нагрузка: умственное напряжение',
    'questionnaire.burdenEffort': 'Нагрузка: усилие',
    'questionnaire.burdenFrustration': 'Нагрузка: фрустрация',
    'questionnaire.trust': 'Доверие / опора на ИИ',
    'questionnaire.usefulness': 'Полезность',
    'questionnaire.submit': 'Отправить анкету',
    'finalSubmit.title': 'Требуется финальная отправка',
    'finalSubmit.ready': 'Все обязательные раунды и анкеты завершены.',
    'finalSubmit.note': 'Выполните финальную отправку, чтобы завершить сессию и открыть экран завершения.',
    'finalSubmit.button': 'Финальная отправка',
    'finalSubmit.submitting': 'Отправка...',
    'completion.title': 'Завершено',
    'completion.thanks': 'Спасибо за участие в этом пилотном исследовательском задании.',
    'completion.done': 'Ваша сессия завершена.',
    'completion.code': 'Код завершения',
  },
};
