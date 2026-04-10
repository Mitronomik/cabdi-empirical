export type DiagnosticGroupKey = 'dataQuality' | 'runShape' | 'behavioralAnomaly' | 'budgetContract' | 'other';

export interface BudgetFlag {
  condition?: string;
  severity?: string;
  kind?: string;
  message?: string;
  observed?: number;
  reference?: number;
  cap?: number;
}

export interface DiagnosticIssue {
  id: string;
  group: DiagnosticGroupKey;
  severity: 'error' | 'warning';
  title: string;
  detail: string;
}

function toNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function issueFromWarning(warning: string, index: number): DiagnosticIssue {
  const lowered = warning.toLowerCase();
  if (lowered.includes('missing core log fields') || lowered.includes('schema') || lowered.includes('missing summary')) {
    return {
      id: `warning-${index}`,
      group: 'dataQuality',
      severity: 'warning',
      title: 'Data quality',
      detail: warning,
    };
  }
  if (lowered.includes('trial-summary count differs') || lowered.includes('partial') || lowered.includes('no sessions')) {
    return {
      id: `warning-${index}`,
      group: 'runShape',
      severity: 'warning',
      title: 'Run shape / logging completeness',
      detail: warning,
    };
  }
  if (lowered.includes('verification') || lowered.includes('reason') || lowered.includes('evidence')) {
    return {
      id: `warning-${index}`,
      group: 'behavioralAnomaly',
      severity: 'warning',
      title: 'Behavioral anomaly',
      detail: warning,
    };
  }
  if (lowered.includes('budget')) {
    return {
      id: `warning-${index}`,
      group: 'budgetContract',
      severity: 'warning',
      title: 'Budget contract',
      detail: warning,
    };
  }
  return {
    id: `warning-${index}`,
    group: 'other',
    severity: 'warning',
    title: 'Other',
    detail: warning,
  };
}

function formatBudgetFlagMessage(flag: BudgetFlag): string {
  const condition = flag.condition ? `Condition ${flag.condition}: ` : '';
  const observed = toNumber(flag.observed);
  const reference = toNumber(flag.reference);
  if (flag.kind === 'text_tolerance_exceeded' || flag.kind === 'display_tolerance_exceeded' || flag.kind === 'interaction_tolerance_exceeded') {
    if (observed !== null && reference !== null) {
      return `${condition}Observed ${observed.toFixed(2)} differs from contract expectation ${reference.toFixed(2)} beyond tolerance.`;
    }
    return `${condition}Observed budget differs from the contract expectation beyond tolerance.`;
  }
  if (flag.kind === 'hard_cap_exceeded') {
    const cap = toNumber(flag.cap);
    if (observed !== null && cap !== null) {
      return `${condition}Observed max extra steps ${observed.toFixed(2)} exceeds allowed cap ${cap.toFixed(2)} per trial.`;
    }
    return `${condition}Observed extra-step usage exceeds the hard cap per trial.`;
  }
  if (flag.kind === 'missing_reference') {
    return `${condition}No contract reference found for this condition/risk pair, so budget matching cannot be verified.`;
  }
  if (flag.kind === 'insufficient_budget_data') {
    return `${condition}Policy decision budget fields are missing in completed-trial logs, so contract checks are incomplete.`;
  }
  return `${condition}${flag.message ?? 'Budget contract warning.'}`;
}

export function buildDiagnosticIssues(raw: Record<string, unknown> | null): DiagnosticIssue[] {
  if (!raw) return [];
  const issues: DiagnosticIssue[] = [];

  const warnings = Array.isArray(raw.warnings) ? raw.warnings.map((item) => String(item)) : [];
  warnings.forEach((warning, index) => {
    issues.push(issueFromWarning(warning, index));
  });

  const budgetFlags = Array.isArray(raw.budget_tolerance_flags) ? (raw.budget_tolerance_flags as BudgetFlag[]) : [];
  budgetFlags.forEach((flag, index) => {
    issues.push({
      id: `budget-flag-${index}`,
      group: 'budgetContract',
      severity: flag.severity === 'error' ? 'error' : 'warning',
      title: 'Budget contract',
      detail: formatBudgetFlagMessage(flag),
    });
  });

  return issues;
}

export function groupOrder(group: DiagnosticGroupKey): number {
  if (group === 'dataQuality') return 0;
  if (group === 'runShape') return 1;
  if (group === 'behavioralAnomaly') return 2;
  if (group === 'budgetContract') return 3;
  return 4;
}

