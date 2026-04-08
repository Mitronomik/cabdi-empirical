export interface TaskFamilyUiSpec {
  defaultResponseOptions: string[];
}

const TASK_FAMILY_UI_REGISTRY: Record<string, TaskFamilyUiSpec> = {
  scam_detection: { defaultResponseOptions: ['scam', 'not_scam'] },
  scam_not_scam: { defaultResponseOptions: ['scam', 'not_scam'] },
};

export function getDefaultResponseOptions(taskFamily: string): string[] {
  const spec = TASK_FAMILY_UI_REGISTRY[String(taskFamily ?? '').trim()];
  return spec?.defaultResponseOptions ?? [];
}
