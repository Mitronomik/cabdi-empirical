import type { MessageKey } from './messages';

export function localizeStatus(t: (key: MessageKey) => string, value: unknown): string {
  const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return t('common.na');

  const mapped: Record<string, MessageKey> = {
    draft: 'common.status.draft',
    active: 'common.status.active',
    paused: 'common.status.paused',
    closed: 'common.status.closed',
    in_progress: 'common.status.in_progress',
    completed: 'common.status.completed',
    awaiting_final_submit: 'common.status.awaiting_final_submit',
    finalized: 'common.status.finalized',
    valid: 'common.status.valid',
    invalid: 'common.status.invalid',
    warning_only: 'common.status.warning_only',
    available: 'common.status.available',
    empty: 'common.status.empty',
    unknown: 'common.status.unknown',
  };

  const key = mapped[raw];
  return key ? t(key) : String(value);
}

export function localizeOperatorError(t: (key: MessageKey) => string, error: unknown): string {
  const raw = error instanceof Error ? error.message : t('common.unknownError');
  const normalized = raw.trim().toLowerCase();

  const mapped: Record<string, MessageKey> = {
    unauthorized: 'common.error.authRequired',
    'invalid username or password': 'common.error.authInvalidCredentials',
    'not authenticated': 'common.error.authRequired',
    'run_slug is required': 'common.error.runSlugRequired',
    'confirm_run_id must match run_id': 'common.error.confirmRunIdMismatch',
  };

  if (mapped[normalized]) {
    return t(mapped[normalized]);
  }

  if (normalized.includes('not found')) {
    return `${t('common.errorPrefix')}: ${t('common.error.notFound')} (${t('common.errorRawPrefix')}: ${raw})`;
  }
  if (normalized.includes('validation') || normalized.includes('unprocessable entity') || normalized.includes('http 422')) {
    return `${t('common.errorPrefix')}: ${t('common.error.validation')} (${t('common.errorRawPrefix')}: ${raw})`;
  }

  return `${t('common.errorPrefix')}: ${raw}`;
}

export function formatProgress(t: (key: MessageKey) => string, block: unknown, trial: unknown): string {
  return t('sessions.progressFormat')
    .replace('{block}', String(block ?? 0))
    .replace('{trial}', String(trial ?? 0));
}
