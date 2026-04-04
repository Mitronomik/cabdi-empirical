import { useLocale } from '../i18n/useLocale';

interface Props {
  completionCode?: string | null;
}

export function CompletionPage({ completionCode }: Props) {
  const { t } = useLocale();

  return (
    <section className="card">
      <h1>{t('completion.title')}</h1>
      <p>{t('completion.thanks')}</p>
      <p>{t('completion.done')}</p>
      <p className="muted">{t('completion.finalizedNote')}</p>
      {completionCode ? (
        <p>
          {t('completion.code')}: {completionCode}
        </p>
      ) : null}
    </section>
  );
}
