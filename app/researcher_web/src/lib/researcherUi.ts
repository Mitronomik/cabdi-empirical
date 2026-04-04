export interface RunSummary {
  run_id: string;
  run_name: string;
  public_slug: string;
  status: string;
  task_family: string;
  launchability_reason: string;
  launchable: boolean;
  linked_stimulus_set_ids: string[];
  created_at?: string;
}

export interface StimulusSetSummary {
  stimulus_set_id: string;
  name: string;
  task_family: string;
  source_format: string;
  n_items: number;
  validation_status: string;
  payload_schema_version?: string;
}

export function parseRunSummary(raw: Record<string, unknown>): RunSummary {
  return {
    run_id: String(raw.run_id ?? ''),
    run_name: String(raw.run_name ?? ''),
    public_slug: String(raw.public_slug ?? ''),
    status: String(raw.status ?? 'draft'),
    task_family: String(raw.task_family ?? ''),
    launchability_reason: String(raw.launchability_reason ?? ''),
    launchable: Boolean(raw.launchable),
    linked_stimulus_set_ids: Array.isArray(raw.linked_stimulus_set_ids)
      ? raw.linked_stimulus_set_ids.map((value) => String(value))
      : [],
    created_at: raw.created_at ? String(raw.created_at) : undefined,
  };
}

export function parseStimulusSetSummary(raw: Record<string, unknown>): StimulusSetSummary {
  return {
    stimulus_set_id: String(raw.stimulus_set_id ?? ''),
    name: String(raw.name ?? ''),
    task_family: String(raw.task_family ?? ''),
    source_format: String(raw.source_format ?? ''),
    n_items: Number(raw.n_items ?? 0),
    validation_status: String(raw.validation_status ?? 'unknown'),
    payload_schema_version: raw.payload_schema_version ? String(raw.payload_schema_version) : undefined,
  };
}

export function runOptionLabel(run: RunSummary): string {
  const slug = run.public_slug ? `/${run.public_slug}` : 'no-public-slug';
  return `${run.run_name || run.run_id} • ${slug} • ${run.status}`;
}

export function pickDefaultRunId(runs: RunSummary[]): string {
  const active = runs.find((item) => item.status === 'active');
  if (active) return active.run_id;
  return runs[0]?.run_id ?? '';
}
