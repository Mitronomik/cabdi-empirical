export interface TaskFamilyUiSpec {
  defaultResponseOptions: string[];
  optionLabelMap?: Record<string, string>;
}

export interface RenderableResponseOption {
  value: string;
  label: string;
}

interface ResponseOptionRecordLike {
  value?: unknown;
  key?: unknown;
  label?: unknown;
  text?: unknown;
}

const TASK_FAMILY_UI_REGISTRY: Record<string, TaskFamilyUiSpec> = {
  scam_detection: {
    defaultResponseOptions: ['scam', 'not_scam'],
    optionLabelMap: {
      scam: 'Scam',
      not_scam: 'Not a scam',
    },
  },
  scam_not_scam: {
    defaultResponseOptions: ['scam', 'not_scam'],
    optionLabelMap: {
      scam: 'Scam',
      not_scam: 'Not a scam',
    },
  },
};

function normalizeOptionEntry(raw: unknown): RenderableResponseOption | null {
  if (typeof raw === 'string') {
    const value = raw.trim();
    if (!value) return null;
    return { value, label: value };
  }

  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const option = raw as ResponseOptionRecordLike;
  const rawValue = option.value ?? option.key;
  const value = typeof rawValue === 'string' ? rawValue.trim() : '';
  if (!value) return null;

  const rawLabel = option.label ?? option.text;
  const label = typeof rawLabel === 'string' && rawLabel.trim() ? rawLabel.trim() : value;

  return { value, label };
}

export function getTaskFamilyUiSpec(taskFamily: string): TaskFamilyUiSpec | undefined {
  return TASK_FAMILY_UI_REGISTRY[String(taskFamily ?? '').trim()];
}

export function getDefaultResponseOptions(taskFamily: string): string[] {
  return getTaskFamilyUiSpec(taskFamily)?.defaultResponseOptions ?? [];
}

export function getRenderableResponseOptions(taskFamily: string, responseOptionsFromPayload: unknown): RenderableResponseOption[] {
  const payloadOptions = Array.isArray(responseOptionsFromPayload)
    ? responseOptionsFromPayload.map((entry) => normalizeOptionEntry(entry)).filter((entry): entry is RenderableResponseOption => Boolean(entry))
    : [];

  if (payloadOptions.length > 0) {
    return payloadOptions;
  }

  const spec = getTaskFamilyUiSpec(taskFamily);
  const defaults = spec?.defaultResponseOptions ?? [];
  const labelMap = spec?.optionLabelMap ?? {};

  return defaults
    .map((value) => String(value).trim())
    .filter(Boolean)
    .map((value) => ({ value, label: labelMap[value] ?? value }));
}

export function formatModelPredictionLabel(value: string, taskFamily: string): string {
  const normalized = String(value ?? '').trim();
  if (!normalized) return '';
  return getTaskFamilyUiSpec(taskFamily)?.optionLabelMap?.[normalized] ?? normalized;
}
