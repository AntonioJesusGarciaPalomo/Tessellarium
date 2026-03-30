// Tessellarium — TypeScript interfaces matching Pydantic models

export type EpistemicState = 'speculative' | 'supported' | 'challenged' | 'inconclusive'
export type OperativeState = 'proposed' | 'designed' | 'in_execution' | 'analyzed' | 'replicated' | 'archived'
export type SafetyVerdict = 'allow' | 'degrade' | 'block'
export type DesignFamily = 'full_factorial' | 'fractional_factorial' | 'latin_square' | 'bibd' | 'orthogonal_array' | 'covering_array' | 'custom'
export type CandidateStrategy = 'max_discrimination' | 'max_robustness' | 'max_coverage'
export type VerificationStatus = 'verified' | 'failed' | 'timeout' | 'not_attempted'

export interface Level {
  id: string
  name: string
  value?: string
  available: boolean
}

export interface Factor {
  id: string
  name: string
  levels: Level[]
  is_blocking_factor: boolean
  is_safety_sensitive: boolean
}

export interface Evidence {
  id: string
  source_type: string
  content: string
  supports_hypotheses: string[]
  challenges_hypotheses: string[]
  confidence: number
  source_reference?: string
}

export interface Hypothesis {
  id: string
  statement: string
  epistemic_state: EpistemicState
  operative_state: OperativeState
  evidence_ids: string[]
  parent_id?: string
  distinguishing_factors: string[]
}

export interface Constraint {
  id?: string
  description: string
  constraint_type: string
  excluded_factor_id?: string | null
  excluded_level_id?: string | null
  excluded_combinations?: Record<string, string>[]
  is_safety_constraint?: boolean
}

export interface ExperimentalRun {
  id: string
  combination: Record<string, string>
  result_summary?: string
  evidence_ids: string[]
}

export interface DesignMatrix {
  rows: Record<string, string>[]
  num_runs: number
  design_family: DesignFamily
  design_properties: Record<string, any>
  verification_status: VerificationStatus
  verification_details?: string
}

export interface DiscriminationPair {
  hypothesis_a_id: string
  hypothesis_b_id: string
  discriminating_combinations: Record<string, string>[]
  discrimination_power: number
}

export interface DecisionCard {
  recommendation: string
  why: string
  evidence_used: string[]
  assumptions: string[]
  counterevidence_or_limits: string[]
  what_would_change_mind: string
}

export interface AffectedPair {
  pair: string
  excluded_runs: number
  total_discriminating: number
  lost_fraction: number
}

export interface ConstraintCost {
  constraint_id: string
  constraint_description: string
  affected_hypothesis_pairs: AffectedPair[]
}

export interface ExperimentCandidate {
  id: string
  strategy: CandidateStrategy
  design_matrix: DesignMatrix
  discrimination_pairs: DiscriminationPair[]
  total_discrimination_score: number
  justification: string
  constraint_costs: ConstraintCost[]
  critique?: string
  decision_card?: DecisionCard
}

export interface CoverageCell {
  combination: Record<string, string>
  is_tested: boolean
  run_id?: string
  is_discriminative_for: string[]
  is_excluded: boolean
  exclusion_reason?: string
}

export interface ProblemSpace {
  id: string
  created_at: string
  updated_at: string
  objective: string
  factors: Factor[]
  hypotheses: Hypothesis[]
  evidence: Evidence[]
  constraints: Constraint[]
  completed_runs: ExperimentalRun[]
  total_combinations: number
  tested_combinations: number
  coverage_map: CoverageCell[]
  candidates: ExperimentCandidate[]
  safety_verdict: SafetyVerdict
  safety_notes: string[]
  max_runs_budget?: number
  protocol_filename?: string
  csv_filename?: string
  image_filename?: string
}

export interface UploadResponse {
  session_id: string
  problem_space: ProblemSpace
}

export interface CompileResponse {
  session_id: string
  problem_space: ProblemSpace
  candidates: ExperimentCandidate[]
  safety_verdict: SafetyVerdict
  safety_notes: string[]
}

export interface SessionSummary {
  id: string
  objective: string
  created_at: string
  updated_at: string
}
