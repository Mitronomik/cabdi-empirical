import { describe, expect, it } from 'vitest';

import { buildDiagnosticIssues } from '../lib/diagnosticsUi';

describe('buildDiagnosticIssues', () => {
  it('groups and prioritizes budget-contract anomalies with readable messages', () => {
    const issues = buildDiagnosticIssues({
      warnings: ['Missing core log fields detected: 5'],
      budget_tolerance_flags: [
        {
          condition: 'cabdi_lite',
          severity: 'warning',
          kind: 'display_tolerance_exceeded',
          observed: 3.2,
          reference: 2.0,
        },
        {
          condition: 'cabdi_lite',
          severity: 'error',
          kind: 'hard_cap_exceeded',
          observed: 3,
          cap: 1,
        },
      ],
    });

    expect(issues).toHaveLength(3);
    expect(issues.find((issue) => issue.group === 'dataQuality')).toBeTruthy();
    expect(issues.filter((issue) => issue.group === 'budgetContract')).toHaveLength(2);
    expect(issues.some((issue) => issue.detail.includes('contract expectation'))).toBe(true);
    expect(issues.some((issue) => issue.detail.includes('allowed cap'))).toBe(true);
  });
});

