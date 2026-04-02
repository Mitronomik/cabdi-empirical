import { useState } from 'react';

interface Props {
  blockId: string;
  onSubmit: (payload: { burden: number; trust: number; usefulness: number }) => void;
  loading: boolean;
}

export function BlockQuestionnairePage({ blockId, onSubmit, loading }: Props) {
  const [mentalDemand, setMentalDemand] = useState(50);
  const [effort, setEffort] = useState(50);
  const [frustration, setFrustration] = useState(50);
  const [trust, setTrust] = useState(50);
  const [usefulness, setUsefulness] = useState(50);

  return (
    <section className="card">
      <h2>Block questionnaire ({blockId})</h2>
      <p>Rate each item from 0 to 100.</p>

      <label>Burden: mental demand ({mentalDemand})</label>
      <input type="range" min={0} max={100} value={mentalDemand} onChange={(e) => setMentalDemand(Number(e.target.value))} />

      <label>Burden: effort ({effort})</label>
      <input type="range" min={0} max={100} value={effort} onChange={(e) => setEffort(Number(e.target.value))} />

      <label>Burden: frustration ({frustration})</label>
      <input type="range" min={0} max={100} value={frustration} onChange={(e) => setFrustration(Number(e.target.value))} />

      <label>Trust / reliance ({trust})</label>
      <input type="range" min={0} max={100} value={trust} onChange={(e) => setTrust(Number(e.target.value))} />

      <label>Usefulness ({usefulness})</label>
      <input type="range" min={0} max={100} value={usefulness} onChange={(e) => setUsefulness(Number(e.target.value))} />

      <button
        type="button"
        disabled={loading}
        onClick={() =>
          onSubmit({
            burden: Math.round((mentalDemand + effort + frustration) / 3),
            trust,
            usefulness,
          })
        }
      >
        Submit questionnaire
      </button>
    </section>
  );
}
