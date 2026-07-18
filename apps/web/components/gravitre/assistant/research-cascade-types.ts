"""Adaptive research cascade — shared payload types for chat UI."""
"use client"

export type ResearchScopeOption = {
  scope: string
  label: string
  description: string
  enabled: boolean
  disabled_reason?: string | null
}

export type CascadeStageProgress = {
  stage: string
  label: string
  status: "completed" | "empty" | "skipped" | "pending"
  detail?: string | null
}

export type ResearchTopSource = {
  source_name?: string | null
  source_type?: string | null
  assignment_id?: string | null
  score?: number | null
  match_tier?: string | null
}

export type ResearchActionSuggestion = {
  integration?: string
  invoke_action?: string
  label?: string
  requires_approval?: boolean
  rationale?: string
  source?: string
}

export type ResearchCascadePayload = {
  internal_thin?: boolean
  suggest_broaden?: boolean
  prompt_message?: string | null
  options?: ResearchScopeOption[]
  research_scope?: string
  internet_research_enabled?: boolean
  retrieval_score?: number | null
  source_count?: number | null
  confidence_band?: "high" | "medium" | "low" | "unknown"
  top_sources?: ResearchTopSource[]
  source_breakdown?: Record<string, number>
  active_stages?: string[]
  stage_order?: string[]
  stage_progress?: CascadeStageProgress[]
  progress_steps?: string[]
  internet_research?: {
    ran?: boolean
    result_count?: number
    skipped_reason?: string | null
    error?: string | null
  }
  intelligence_packs?: {
    ran?: boolean
    result_count?: number
    pack_ids?: string[]
    catalog_matches?: number
    signal_count?: number
    entity_count?: number
  }
  research_actions?: ResearchActionSuggestion[]
  has_gated_actions?: boolean
}

export function formatConfidenceBand(band?: string | null): string {
  switch (band) {
    case "high":
      return "High confidence"
    case "medium":
      return "Medium confidence"
    case "low":
      return "Low confidence"
    default:
      return "Confidence unknown"
  }
}

export function formatRetrievalScore(score?: number | null): string {
  if (score == null || Number.isNaN(Number(score))) return "—"
  return `${Math.round(Number(score) * 100)}%`
}

export function kindLabel(kind: string): string {
  switch (kind) {
    case "knowledge":
      return "Internal knowledge"
    case "memory":
      return "Agent memory"
    case "graph":
      return "Knowledge graph"
    case "internet":
      return "Internet research"
    case "intelligence_pack":
      return "Intelligence pack"
    case "hybrid_memory":
      return "Hybrid memory"
    default:
      return kind.replace(/_/g, " ")
  }
}
