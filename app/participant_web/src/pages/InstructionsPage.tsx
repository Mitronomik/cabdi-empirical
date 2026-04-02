interface Props {
  participantId: string;
  setParticipantId: (value: string) => void;
  onStart: () => void;
  loading: boolean;
}

export function InstructionsPage({ participantId, setParticipantId, onStart, loading }: Props) {
  return (
    <section className="card">
      <h1>Instructions</h1>
      <ul>
        <li>You will classify cases as part of a research task.</li>
        <li>AI assistance may be shown during some trials.</li>
        <li>The AI can be wrong.</li>
        <li>Do not blindly follow the AI recommendation.</li>
        <li>You will complete practice trials before the main blocks.</li>
      </ul>
      <label htmlFor="participant-id">Participant ID</label>
      <input
        id="participant-id"
        value={participantId}
        onChange={(e) => setParticipantId(e.target.value)}
        placeholder="e.g., p_001"
      />
      <button type="button" disabled={!participantId || loading} onClick={onStart}>
        Start practice
      </button>
    </section>
  );
}
