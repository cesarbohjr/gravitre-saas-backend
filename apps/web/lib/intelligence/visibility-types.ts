/** Wave E — decision transparency and visibility API shapes (no chain-of-thought). */

export type AlternativePathsConsidered = {
  alternative_strategy_count?: number
  selected_strategy?: string | null
  guidance_strength?: number | null
}

export type LearningConfidenceView = {
  level?: string
  sample_count?: number | null
  noise?: string | null
  insufficient_data?: boolean
}

export type DomainHealthEntry = {
  domain?: string
  department?: string | null
  subdomain?: string | null
  health_score?: number | null
  health_label?: string
  learning_confidence?: string
  freshness?: string
  retrieval_effectiveness?: number | null
  optimization_recommendations?: number
}

export type IntelligenceMaturityView = {
  level?: number
  label?: string
  description?: string
  factors?: Record<string, unknown>
}

export type DecisionTransparencyEnvelope = {
  decision_type?: string
  confidence?: number
  confidence_band?: string
  evidence_used?: Array<Record<string, unknown>>
  sources_used?: Array<Record<string, unknown>>
  freshness_status?: string | null
  domain_context?: Record<string, unknown> | null
  optimization_signals?: Array<Record<string, unknown>>
  learning_confidence?: LearningConfidenceView | null
  known_gaps?: string[]
  alternative_paths_considered?: AlternativePathsConsidered | null
  retrieval_summary?: Record<string, unknown> | null
  trust_health?: Record<string, unknown> | null
  advisory_only?: boolean
  summary?: string | null
  missing_context?: string[]
  extension_points?: Record<string, unknown>
}

export type ExecutiveIntelligenceSummary = {
  org_id?: string
  intelligence_score?: number | null
  score_label?: string
  score_breakdown?: Record<string, unknown>
  score_weights?: Record<string, number>
  maturity?: IntelligenceMaturityView | null
  domain_health?: DomainHealthEntry[]
  top_performing_domains?: string[]
  weak_domains?: string[]
  missing_knowledge_areas?: string[]
  optimization_opportunities?: number
  advisory_only?: boolean
}

export type VisibilityTrustHealth = {
  status?: string
  org_id?: string
  confidence?: { average?: number | null; band?: string }
  freshness?: Record<string, unknown>
  stale_source_warnings?: string[]
  learning_confidence?: LearningConfidenceView | null
  optimization_state?: {
    pending_recommendations?: number
    advisory_only?: boolean
    auto_execution_enabled?: boolean
  }
  provenance_quality?: Record<string, unknown>
  data_coverage?: string
  known_limitations?: string[]
  advisory_only?: boolean
}

export type VisibilityDomainHealth = {
  status?: string
  org_id?: string
  domains?: DomainHealthEntry[]
  healthy_domains?: string[]
  needs_attention_domains?: string[]
  improving_domains?: string[]
  advisory_only?: boolean
}
