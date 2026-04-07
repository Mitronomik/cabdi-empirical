export interface RunSummary {
  run_id: string;
  run_name: string;
  public_slug: string;
  invite_url: string;
  status: string;
  run_status: string;
  task_family: string;
  launchability_reason: string;
  launchable: boolean;
  launchability_state: string;
  linked_stimulus_set_ids: string[];
  aggregation_mode?: string;
  practice_stimulus_set_id?: string | null;
  run_summary?: {
    expected_trial_count?: number;
    aggregation_enabled?: boolean;
    practice_item_count?: number;
    main_item_count?: number;
    total_main_items?: number;
    selected_main_bank_ids?: string[];
    selected_practice_bank_id?: string | null;
    selected_practice_bank?: { stimulus_set_id: string; name: string; n_items: number; role: string } | null;
    practice_bank?: { stimulus_set_id: string; name: string; n_items: number; role: string } | null;
    banks?: Array<{ stimulus_set_id: string; name: string; n_items: number; role: string }>;
  };
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
    invite_url: String(raw.invite_url ?? ''),
    status: String(raw.status ?? 'draft'),
    run_status: String(raw.run_status ?? raw.status ?? 'draft'),
    task_family: String(raw.task_family ?? ''),
    launchability_reason: String(raw.launchability_reason ?? ''),
    launchable: Boolean(raw.launchable),
    launchability_state: String(raw.launchability_state ?? (Boolean(raw.launchable) ? 'launchable' : 'not_launchable')),
    linked_stimulus_set_ids: Array.isArray(raw.linked_stimulus_set_ids)
      ? raw.linked_stimulus_set_ids.map((value) => String(value))
      : [],
    aggregation_mode: raw.aggregation_mode ? String(raw.aggregation_mode) : undefined,
    practice_stimulus_set_id: raw.practice_stimulus_set_id ? String(raw.practice_stimulus_set_id) : undefined,
    run_summary:
      raw.run_summary && typeof raw.run_summary === 'object'
        ? (raw.run_summary as {
            expected_trial_count?: number;
            aggregation_enabled?: boolean;
            practice_item_count?: number;
            main_item_count?: number;
            total_main_items?: number;
            selected_main_bank_ids?: string[];
            selected_practice_bank_id?: string | null;
            selected_practice_bank?: { stimulus_set_id: string; name: string; n_items: number; role: string } | null;
            practice_bank?: { stimulus_set_id: string; name: string; n_items: number; role: string } | null;
            banks?: Array<{ stimulus_set_id: string; name: string; n_items: number; role: string }>;
          })
        : undefined,
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

export function runOptionLabelLocalized(run: RunSummary, localizeStatus: (value: unknown) => string): string {
  const slug = run.public_slug ? `/${run.public_slug}` : 'no-public-slug';
  return `${run.run_name || run.run_id} • ${slug} • ${localizeStatus(run.status)}`;
}

export function pickDefaultRunId(runs: RunSummary[]): string {
  const active = runs.find((item) => item.status === 'active');
  if (active) return active.run_id;
  return runs[0]?.run_id ?? '';
}
