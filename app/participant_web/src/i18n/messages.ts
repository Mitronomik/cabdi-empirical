export const SUPPORTED_LOCALES = ['en', 'ru'] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export type MessageKey =
  | 'lang.en'
  | 'lang.ru'
  | 'lang.switcherLabel'
  | 'trial.progressAria'
  | 'assistance.panelAria'
  | 'error.runSlugRequired'
  | 'error.runSlugInvalid'
  | 'error.runNotOpen'
  | 'error.retry'
  | 'error.loadNextTrial'
  | 'error.startSession'
  | 'error.missingSessionState'
  | 'error.submitTrial'
  | 'error.missingQuestionnaireState'
  | 'error.submitQuestionnaire'
  | 'error.missingSessionStateShort'
  | 'error.finalSubmit'
  | 'entry.title'
  | 'entry.missingRun'
  | 'entry.contactCoordinator'
  | 'entry.resumeResumed'
  | 'entry.resumeInvalid'
  | 'entry.resumeFinalized'
  | 'entry.resumeNotResumable'
  | 'consent.title'
  | 'consent.description'
  | 'consent.checkbox'
  | 'common.continue'
  | 'instructions.title'
  | 'instructions.defaultRunTitle'
  | 'instructions.item.classify'
  | 'instructions.item.assistance'
  | 'instructions.item.aiWrong'
  | 'instructions.item.noBlindFollow'
  | 'instructions.item.practice'
  | 'instructions.resumeHint'
  | 'instructions.starting'
  | 'instructions.startPractice'
  | 'trial.progressLabel'
  | 'trial.resumeHint'
  | 'trial.caseTitle'
  | 'trial.noPrompt'
  | 'trial.decisionTitle'
  | 'trial.decisionHelp'
  | 'trial.answerLabel'
  | 'trial.confidenceLow'
  | 'trial.confidenceHigh'
  | 'trial.selfConfidence'
  | 'trial.submit'
  | 'trial.submitHelp'
  | 'common.progressSaved'
  | 'trial.response.scam'
  | 'trial.response.notScam'
  | 'trial.response.yes'
  | 'trial.response.no'
  | 'assistance.title'
  | 'assistance.prediction'
  | 'assistance.modelConfidence'
  | 'assistance.confidence.low'
  | 'assistance.confidence.medium'
  | 'assistance.confidence.high'
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
  | 'questionnaire.blockLabel'
  | 'questionnaire.intro'
  | 'questionnaire.rateItems'
  | 'questionnaire.burdenMental'
  | 'questionnaire.burdenEffort'
  | 'questionnaire.burdenFrustration'
  | 'questionnaire.trust'
  | 'questionnaire.usefulness'
  | 'questionnaire.submit'
  | 'finalSubmit.title'
  | 'finalSubmit.ready'
  | 'finalSubmit.progress'
  | 'finalSubmit.note'
  | 'finalSubmit.resumeUntilSubmit'
  | 'finalSubmit.button'
  | 'finalSubmit.submitting'
  | 'completion.title'
  | 'completion.thanks'
  | 'completion.done'
  | 'completion.finalizedNote'
  | 'completion.code';

export const messages: Record<Locale, Record<MessageKey, string>> = {
  en: {
    'lang.en': 'EN',
    'lang.ru': 'RU',
    'lang.switcherLabel': 'Language switcher',
    'trial.progressAria': 'progress',
    'assistance.panelAria': 'AI assistance panel',
    'error.runSlugRequired': 'This study link is incomplete. Please use the full invitation link.',
    'error.runSlugInvalid': 'This study link could not be found. Please check your invitation link.',
    'error.runNotOpen': 'This study is currently unavailable. Please contact the study coordinator.',
    'error.retry': 'Try again',
    'error.loadNextTrial': 'We could not load the next step. Please try again.',
    'error.startSession': 'Unable to start the study right now. Please try again.',
    'error.missingSessionState': 'We lost your session state. Please restart from your invitation link.',
    'error.submitTrial': 'Your response could not be submitted. Please try again.',
    'error.missingQuestionnaireState': 'Questionnaire state is missing. Please restart from your invitation link.',
    'error.submitQuestionnaire': 'Questionnaire submission failed. Please try again.',
    'error.missingSessionStateShort': 'Session state is missing.',
    'error.finalSubmit': 'Final submission failed. Please try again.',
    'entry.title': 'Study link needed',
    'entry.missingRun': 'To begin, open the invitation link provided by the study team.',
    'entry.contactCoordinator': 'If this keeps happening, contact your study coordinator.',
    'entry.resumeResumed': 'We found your saved progress and will resume this session.',
    'entry.resumeInvalid': 'Saved resume data was invalid, so a new session will be started.',
    'entry.resumeFinalized': 'Your previous session was already finalized. You may start a new session.',
    'entry.resumeNotResumable': 'Your previous session cannot be resumed, so a new session will be started.',
    'consent.title': 'Consent',
    'consent.description': 'This is a research task. Your responses will be recorded for pilot research purposes.',
    'consent.checkbox': 'I consent to participate in this research task.',
    'common.continue': 'Continue',
    'common.progressSaved': 'Progress saved.',
    'instructions.title': 'Before you begin',
    'instructions.defaultRunTitle': 'Pilot study',
    'instructions.item.classify': 'You will review brief cases and choose the best label.',
    'instructions.item.assistance': 'AI assistance may be shown for some cases.',
    'instructions.item.aiWrong': 'The AI can be wrong.',
    'instructions.item.noBlindFollow': 'Make your own judgment and avoid blindly following AI output.',
    'instructions.item.practice': 'You will complete a short practice section first.',
    'instructions.resumeHint': 'If you are interrupted, your progress is saved and you can continue later.',
    'instructions.starting': 'Starting...',
    'instructions.startPractice': 'Start study',
    'trial.progressLabel': 'Progress',
    'trial.resumeHint': 'Progress is saved automatically.',
    'trial.caseTitle': 'Case',
    'trial.noPrompt': 'No prompt provided.',
    'trial.decisionTitle': 'Your response',
    'trial.decisionHelp': 'Use the information above to make your own decision.',
    'trial.answerLabel': 'Choose your answer',
    'trial.confidenceLow': 'Low confidence',
    'trial.confidenceHigh': 'High confidence',
    'trial.selfConfidence': 'How confident are you?',
    'trial.submit': 'Submit response',
    'trial.submitHelp': 'Your response is saved immediately after you submit.',
    'trial.response.scam': 'Scam',
    'trial.response.notScam': 'Not a scam',
    'trial.response.yes': 'Yes',
    'trial.response.no': 'No',
    'assistance.title': 'AI assistance',
    'assistance.prediction': 'AI suggestion',
    'assistance.modelConfidence': 'AI confidence',
    'assistance.confidence.low': 'Low',
    'assistance.confidence.medium': 'Medium',
    'assistance.confidence.high': 'High',
    'assistance.rationale': 'Why the AI suggested this',
    'assistance.defaultRationale': 'No rationale was provided for this case.',
    'assistance.defaultEvidence': 'No supporting evidence was provided for this case.',
    'assistance.showRationale': 'Show why',
    'assistance.showEvidence': 'Show details',
    'assistance.hideEvidence': 'Hide details',
    'assistance.verifyHint': 'Reminder: AI may be wrong. Verify before you submit.',
    'assistance.forcedCheckbox': 'I reviewed the AI output and made my own decision.',
    'assistance.secondLook': 'I completed a second look',
    'questionnaire.title': 'Block questionnaire',
    'questionnaire.blockLabel': 'Completed section',
    'questionnaire.intro': 'Before continuing, please complete this short check-in about the section you just finished.',
    'questionnaire.rateItems': 'Rate each item from 0 to 100.',
    'questionnaire.burdenMental': 'Burden: mental demand',
    'questionnaire.burdenEffort': 'Burden: effort',
    'questionnaire.burdenFrustration': 'Burden: frustration',
    'questionnaire.trust': 'Trust / reliance',
    'questionnaire.usefulness': 'Usefulness',
    'questionnaire.submit': 'Continue',
    'finalSubmit.title': 'Final confirmation required',
    'finalSubmit.ready': 'You have finished all required steps.',
    'finalSubmit.progress': 'Completed trials',
    'finalSubmit.note': 'Select Final submit to lock your responses and complete the study.',
    'finalSubmit.resumeUntilSubmit': 'Until final submit, your session is saved but not fully completed.',
    'finalSubmit.button': 'Final submit',
    'finalSubmit.submitting': 'Submitting...',
    'completion.title': 'Study complete',
    'completion.thanks': 'Thank you for your participation.',
    'completion.done': 'Your responses were saved successfully.',
    'completion.finalizedNote': 'Your session is finalized and cannot be resumed.',
    'completion.code': 'Completion code',
  },
  ru: {
    'lang.en': 'EN',
    'lang.ru': 'RU',
    'lang.switcherLabel': 'Переключатель языка',
    'trial.progressAria': 'прогресс',
    'assistance.panelAria': 'Панель помощи ИИ',
    'error.runSlugRequired': 'Ссылка на исследование неполная. Откройте полную ссылку-приглашение.',
    'error.runSlugInvalid': 'Не удалось найти это исследование. Проверьте ссылку-приглашение.',
    'error.runNotOpen': 'Исследование сейчас недоступно. Свяжитесь с координатором.',
    'error.retry': 'Повторить',
    'error.loadNextTrial': 'Не удалось загрузить следующий шаг. Повторите попытку.',
    'error.startSession': 'Сейчас не удалось начать исследование. Повторите попытку.',
    'error.missingSessionState': 'Состояние сессии потеряно. Перезапустите по ссылке-приглашению.',
    'error.submitTrial': 'Не удалось отправить ответ. Повторите попытку.',
    'error.missingQuestionnaireState': 'Состояние анкеты отсутствует. Перезапустите по ссылке-приглашению.',
    'error.submitQuestionnaire': 'Не удалось отправить анкету. Повторите попытку.',
    'error.missingSessionStateShort': 'Состояние сессии отсутствует.',
    'error.finalSubmit': 'Не удалось выполнить финальную отправку. Повторите попытку.',
    'entry.title': 'Нужна ссылка на исследование',
    'entry.missingRun': 'Чтобы начать, откройте ссылку-приглашение от исследовательской команды.',
    'entry.contactCoordinator': 'Если проблема повторяется, свяжитесь с координатором исследования.',
    'entry.resumeResumed': 'Мы нашли сохраненный прогресс и продолжим эту сессию.',
    'entry.resumeInvalid': 'Сохраненные данные продолжения некорректны, будет начата новая сессия.',
    'entry.resumeFinalized': 'Предыдущая сессия уже финализирована. Вы можете начать новую сессию.',
    'entry.resumeNotResumable': 'Предыдущую сессию нельзя продолжить, будет начата новая сессия.',
    'consent.title': 'Согласие',
    'consent.description': 'Это исследовательское задание. Ваши ответы будут записаны для пилотного исследования.',
    'consent.checkbox': 'Я согласен(на) участвовать в этом исследовательском задании.',
    'common.continue': 'Продолжить',
    'common.progressSaved': 'Прогресс сохранен.',
    'instructions.title': 'Перед началом',
    'instructions.defaultRunTitle': 'Пилотное исследование',
    'instructions.item.classify': 'Вам нужно просматривать короткие кейсы и выбирать лучший вариант ответа.',
    'instructions.item.assistance': 'Для некоторых кейсов будет показана помощь ИИ.',
    'instructions.item.aiWrong': 'ИИ может ошибаться.',
    'instructions.item.noBlindFollow': 'Принимайте собственное решение и не следуйте ИИ вслепую.',
    'instructions.item.practice': 'Сначала будет короткая тренировочная часть.',
    'instructions.resumeHint': 'Если вас прервут, прогресс сохранится, и вы сможете продолжить позже.',
    'instructions.starting': 'Запуск...',
    'instructions.startPractice': 'Начать исследование',
    'trial.progressLabel': 'Прогресс',
    'trial.resumeHint': 'Прогресс сохраняется автоматически.',
    'trial.caseTitle': 'Кейс',
    'trial.noPrompt': 'Текст задания не предоставлен.',
    'trial.decisionTitle': 'Ваш ответ',
    'trial.decisionHelp': 'Используйте информацию выше и примите собственное решение.',
    'trial.answerLabel': 'Выберите ваш ответ',
    'trial.confidenceLow': 'Низкая уверенность',
    'trial.confidenceHigh': 'Высокая уверенность',
    'trial.selfConfidence': 'Насколько вы уверены?',
    'trial.submit': 'Отправить ответ',
    'trial.submitHelp': 'Ответ сохраняется сразу после отправки.',
    'trial.response.scam': 'Мошенничество',
    'trial.response.notScam': 'Не мошенничество',
    'trial.response.yes': 'Да',
    'trial.response.no': 'Нет',
    'assistance.title': 'Помощь ИИ',
    'assistance.prediction': 'Подсказка ИИ',
    'assistance.modelConfidence': 'Уверенность ИИ',
    'assistance.confidence.low': 'Низкая',
    'assistance.confidence.medium': 'Средняя',
    'assistance.confidence.high': 'Высокая',
    'assistance.rationale': 'Почему ИИ так считает',
    'assistance.defaultRationale': 'Для этого кейса обоснование не предоставлено.',
    'assistance.defaultEvidence': 'Для этого кейса подтверждающие детали не предоставлены.',
    'assistance.showRationale': 'Показать почему',
    'assistance.showEvidence': 'Показать детали',
    'assistance.hideEvidence': 'Скрыть детали',
    'assistance.verifyHint': 'Напоминание: ИИ может ошибаться. Проверьте ответ перед отправкой.',
    'assistance.forcedCheckbox': 'Я проверил(а) вывод ИИ и принял(а) собственное решение.',
    'assistance.secondLook': 'Я выполнил(а) повторную проверку',
    'questionnaire.title': 'Анкета по блоку',
    'questionnaire.blockLabel': 'Завершенный раздел',
    'questionnaire.intro': 'Перед продолжением заполните короткую анкету по только что завершенному разделу.',
    'questionnaire.rateItems': 'Оцените каждый пункт от 0 до 100.',
    'questionnaire.burdenMental': 'Нагрузка: умственное напряжение',
    'questionnaire.burdenEffort': 'Нагрузка: усилие',
    'questionnaire.burdenFrustration': 'Нагрузка: фрустрация',
    'questionnaire.trust': 'Доверие / опора на ИИ',
    'questionnaire.usefulness': 'Полезность',
    'questionnaire.submit': 'Продолжить',
    'finalSubmit.title': 'Нужно финальное подтверждение',
    'finalSubmit.ready': 'Вы завершили все обязательные шаги.',
    'finalSubmit.progress': 'Завершено раундов',
    'finalSubmit.note': 'Нажмите «Финальная отправка», чтобы зафиксировать ответы и завершить исследование.',
    'finalSubmit.resumeUntilSubmit': 'До финальной отправки сессия сохранена, но еще не считается полностью завершенной.',
    'finalSubmit.button': 'Финальная отправка',
    'finalSubmit.submitting': 'Отправка...',
    'completion.title': 'Исследование завершено',
    'completion.thanks': 'Спасибо за участие.',
    'completion.done': 'Ваши ответы успешно сохранены.',
    'completion.finalizedNote': 'Сессия финализирована и больше не может быть продолжена.',
    'completion.code': 'Код завершения',
  },
};
