interface Props {
  consentChecked: boolean;
  setConsentChecked: (value: boolean) => void;
  onContinue: () => void;
}

export function ConsentPage({ consentChecked, setConsentChecked, onContinue }: Props) {
  return (
    <section className="card">
      <h1>Consent</h1>
      <p>This is a research task. Your responses will be recorded for pilot research purposes.</p>
      <label>
        <input
          type="checkbox"
          checked={consentChecked}
          onChange={(e) => setConsentChecked(e.target.checked)}
        />
        I consent to participate in this research task.
      </label>
      <button type="button" disabled={!consentChecked} onClick={onContinue}>
        Continue
      </button>
    </section>
  );
}
