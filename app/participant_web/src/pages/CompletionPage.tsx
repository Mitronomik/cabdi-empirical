interface Props {
  completionCode?: string | null;
}

export function CompletionPage({ completionCode }: Props) {
  return (
    <section className="card">
      <h1>Complete</h1>
      <p>Thank you for participating in this pilot research task.</p>
      <p>Your session is complete.</p>
      {completionCode ? <p>Completion code: {completionCode}</p> : null}
    </section>
  );
}
