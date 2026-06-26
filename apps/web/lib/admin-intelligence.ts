/**
 * Shared types + server helper for the Admin Intelligence console.
 *
 * Covers three subsystems surfaced in /admin/intelligence:
 *   - Memory Promotion (v4): candidate agent memories that may be promoted to
 *     org scope, plus a record of what was auto/manually promoted.
 *   - Entity Relationships (v6): extracted entities and the typed edges between
 *     them, with extraction confidence.
 *   - Evaluation (v7): composite response-quality score, its weighted
 *     components, sampled scored responses, and the learning-to-rank status.
 *
 * Honest-by-default: every shape has a zeroed/inactive default. When the
 * FastAPI backend is configured (FASTAPI_BASE_URL) the routes proxy real data;
 * otherwise they return these defaults so the UI never implies live ML systems
 * are running when they are not.
 */

import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

/** True when a real backend is wired up and routes should proxy to it. */
export function hasIntelligenceBackend(): boolean {
  return Boolean(process.env.FASTAPI_BASE_URL?.trim())
}

/**
 * Proxy to the FastAPI backend when configured, otherwise return an honest
 * default payload (HTTP 200) so the client renders calm empty/inactive states
 * rather than an error. Never fabricates data.
 */
export async function proxyOrDefault(
  request: NextRequest,
  backendPath: string,
  fallback: unknown,
): Promise<NextResponse> {
  if (hasIntelligenceBackend()) {
    return proxyToFastApi(request, backendPath)
  }
  return new NextResponse(JSON.stringify(fallback), { status: 200, headers: JSON_HEADERS })
}

// ============ Overview ============

export interface QueryCluster {
  id: string
  label: string
  queryCount: number
  exampleQueries: string[]
  avgScore: number | null
}

export interface GlossaryTerm {
  id: string
  term: string
  definition: string
  sourceCount: number
}

export interface KnowledgeGap {
  id: string
  topic: string
  missedQueries: number
  lastSeenAt: string | null
}

export interface IntelligenceOverview {
  clusters: QueryCluster[]
  glossary: GlossaryTerm[]
  gaps: KnowledgeGap[]
  generatedAt: string | null
}

// ============ Memory Promotion (v4) ============

export type MemoryScope = "agent" | "org"

export interface PromotionCandidate {
  id: string
  content: string
  category: string
  agentId: string | null
  agentName: string | null
  usageCount: number
  lastUsedAt: string | null
  /** Model/heuristic confidence that this memory generalizes beyond one agent. */
  confidence: number
  suggestedScope: MemoryScope
  reason: string
}

export interface PromotedMemory {
  id: string
  content: string
  scope: MemoryScope
  promotedAt: string
  promotedBy: "auto" | "admin"
  agentName: string | null
}

export interface MemoryPromotionData {
  candidates: PromotionCandidate[]
  promoted: PromotedMemory[]
  /** Whether the backend auto-promotes high-confidence memories. */
  autoPromotionEnabled: boolean
  /** Confidence at/above which a candidate is eligible for auto-promotion. */
  autoPromotionThreshold: number
  generatedAt: string | null
}

// ============ Entity Relationships (v6) ============

export interface IntelligenceEntity {
  id: string
  name: string
  type: string
  mentions: number
}

export interface EntityRelationship {
  id: string
  sourceId: string
  sourceName: string
  targetId: string
  targetName: string
  type: string
  /** Extraction confidence in [0, 1]. */
  confidence: number
  mentions: number
}

export interface RelationshipsData {
  entities: IntelligenceEntity[]
  relationships: EntityRelationship[]
  generatedAt: string | null
}

// ============ Evaluation (v7) ============

export interface EvaluationComponent {
  key: string
  label: string
  /** Component score in [0, 1]. */
  score: number
  /** Weight in [0, 1]; weights across components sum to 1. */
  weight: number
}

export interface ResponseSample {
  id: string
  query: string
  compositeScore: number
  ragQuality: number
  userFeedback: number | null
  sourceReliability: number
  createdAt: string
}

/**
 * Learning-to-rank status (v7). The whole point of v7's design is that the
 * learned weight can never destabilize ranking, so activity AND the safe bound
 * are always reported together.
 */
export interface LearningToRankStatus {
  /** True once trained on >= trainingThreshold examples for this org. */
  active: boolean
  trainingExamples: number
  trainingThreshold: number
  /** v5 fixed fallback weight used while inactive. */
  defaultWeight: number
  /** The learned weight, only when active; null while using the default. */
  learnedWeight: number | null
  /** Hard safety bounds the learned weight is clamped to. */
  weightBounds: { min: number; max: number }
  lastTrainedAt: string | null
}

export interface EvaluationData {
  /** Overall composite score in [0, 1], or null when no responses scored yet. */
  compositeScore: number | null
  components: EvaluationComponent[]
  samples: ResponseSample[]
  learningToRank: LearningToRankStatus
  generatedAt: string | null
}

// ============ Honest defaults ============

export const DEFAULT_OVERVIEW: IntelligenceOverview = {
  clusters: [],
  glossary: [],
  gaps: [],
  generatedAt: null,
}

export const DEFAULT_MEMORY_PROMOTION: MemoryPromotionData = {
  candidates: [],
  promoted: [],
  autoPromotionEnabled: false,
  autoPromotionThreshold: 0.85,
  generatedAt: null,
}

export const DEFAULT_RELATIONSHIPS: RelationshipsData = {
  entities: [],
  relationships: [],
  generatedAt: null,
}

/**
 * Default evaluation: composite weights mirror v7's design
 * (RAG quality 40%, user feedback 40%, source reliability 20%), with the
 * learning-to-rank ranker inactive and falling back to v5's fixed 0.15 weight,
 * bounded to a safe [0.05, 0.35] range.
 */
export const DEFAULT_EVALUATION: EvaluationData = {
  compositeScore: null,
  components: [
    { key: "rag_quality", label: "RAG quality", score: 0, weight: 0.4 },
    { key: "user_feedback", label: "User feedback", score: 0, weight: 0.4 },
    { key: "source_reliability", label: "Source reliability", score: 0, weight: 0.2 },
  ],
  samples: [],
  learningToRank: {
    active: false,
    trainingExamples: 0,
    trainingThreshold: 100,
    defaultWeight: 0.15,
    learnedWeight: null,
    weightBounds: { min: 0.05, max: 0.35 },
    lastTrainedAt: null,
  },
  generatedAt: null,
}
