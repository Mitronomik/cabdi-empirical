export type RationaleMode = 'none' | 'inline' | 'on_click';
export type VerificationMode = 'none' | 'soft_prompt' | 'forced_checkbox' | 'forced_second_look';
export type CompressionMode = 'none' | 'medium' | 'high';

export interface PolicyDecision {
  condition: string;
  risk_bucket: 'low' | 'moderate' | 'extreme';
  show_prediction: boolean;
  show_confidence: boolean;
  show_rationale: RationaleMode;
  show_evidence: boolean;
  verification_mode: VerificationMode;
  compression_mode: CompressionMode;
  max_extra_steps: number;
  ui_help_level: string;
  ui_verification_level: string;
  budget_signature: Record<string, unknown>;
}

export interface StimulusItem {
  stimulus_id: string;
  task_family: string;
  content_type: 'text' | 'image' | 'vignette';
  payload: Record<string, unknown>;
  true_label: string;
  difficulty_prior: 'low' | 'medium' | 'high';
  model_prediction: string;
  model_confidence: 'low' | 'medium' | 'high';
  model_correct: boolean;
  eligible_sets: string[];
  notes?: string;
}

export interface TrialPayload {
  block_id: string;
  trial_id: string;
  stimulus: StimulusItem;
  policy_decision: PolicyDecision;
  self_confidence_scale: {
    min: number;
    max: number;
    step: number;
  };
  progress?: {
    completed_trials: number;
    total_trials: number;
    current_ordinal: number;
  };
}

export interface QuestionnairePayload {
  burden: number;
  trust: number;
  usefulness: number;
}
