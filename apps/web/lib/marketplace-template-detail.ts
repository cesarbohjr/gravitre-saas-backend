/**
 * Read-only helpers for the marketplace template detail page. Everything here
 * is derived from the asset's own definition (config.steps and friends); when
 * the definition does not say something, the helpers return null/empty so the
 * page can leave the section out instead of inventing content.
 */
import type { MarketplaceAssetDetail } from "@/types/api"

type Row = Record<string, unknown>

function isRow(value: unknown): value is Row {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function text(value: unknown): string | null {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function humanise(value: string): string {
  const spaced = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : spaced
}

export interface TemplateStep {
  id: string
  title: string
  detail: string | null
  /** Tool action the step calls, e.g. "slack.post_message". */
  tool: string | null
  approval: boolean
}

const APPROVAL_TYPES = new Set([
  "approval",
  "approval_gate",
  "human_approval",
  "human_review",
  "review_gate",
  "manual_approval",
])

function rawSteps(config: Row | undefined): unknown[] {
  if (!config) return []
  const candidates: unknown[] = [
    config.steps,
    config.workflow_steps,
    config.workflowSteps,
    isRow(config.workflow) ? config.workflow.steps : undefined,
    isRow(config.definition) ? config.definition.steps : undefined,
  ]
  for (const candidate of candidates) {
    if (Array.isArray(candidate) && candidate.length > 0) return candidate
  }
  return []
}

function stepNeedsApproval(step: Row, type: string): boolean {
  if (APPROVAL_TYPES.has(type)) return true
  const config = isRow(step.config) ? step.config : {}
  const metadata = isRow(step.metadata) ? step.metadata : {}
  return [
    step.requires_approval,
    step.requiresApproval,
    config.requires_approval,
    config.requiresApproval,
    metadata.requires_approval,
    metadata.requiresApproval,
  ].some((flag) => flag === true)
}

/** Steps from the asset's workflow definition, in order. */
export function templateSteps(asset: Pick<MarketplaceAssetDetail, "config">): TemplateStep[] {
  const config = isRow(asset.config) ? asset.config : undefined
  return rawSteps(config)
    .filter(isRow)
    .map((step, index) => {
      const type = String(step.type ?? "").toLowerCase()
      const config = isRow(step.config) ? step.config : {}
      const metadata = isRow(step.metadata) ? step.metadata : {}
      const id = text(step.id) ?? `step-${index + 1}`
      const title =
        text(step.name) ?? text(step.title) ?? text(step.label) ?? humanise(id)
      const detail =
        text(step.description) ??
        text(metadata.task) ??
        text(metadata.description) ??
        text(config.description) ??
        null
      const tool =
        text(config.action) ??
        text(config.tool_action) ??
        text(step.action) ??
        text(metadata.action) ??
        null
      return { id, title, detail, tool, approval: stepNeedsApproval(step, type) }
    })
}

export function approvalGateCount(steps: TemplateStep[]): number {
  return steps.filter((step) => step.approval).length
}

export interface TemplateOutput {
  title: string
  kind: string | null
  description: string | null
  /** Section headings of the output, shown as skeleton rows in the sample. */
  sections: string[]
  /** Metric names, shown with [#] placeholders in the sample. */
  metrics: string[]
  /** Where the output lands ("Reports", "Slack"), when the definition says. */
  destination: string | null
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => (isRow(item) ? text(item.name) ?? text(item.title) ?? text(item.label) : text(item)))
    .filter((item): item is string => Boolean(item))
}

function normaliseOutput(value: unknown, fallbackTitle: string): TemplateOutput | null {
  const asText = text(value)
  if (asText) {
    return { title: fallbackTitle, kind: null, description: asText, sections: [], metrics: [], destination: null }
  }
  if (!isRow(value)) return null
  const title = text(value.title) ?? text(value.name) ?? text(value.label) ?? fallbackTitle
  return {
    title,
    kind: text(value.kind) ?? text(value.type) ?? text(value.format) ?? null,
    description: text(value.description) ?? text(value.summary) ?? null,
    sections: stringList(value.sections),
    metrics: stringList(value.metrics ?? value.fields),
    destination: text(value.destination) ?? text(value.lands_in) ?? text(value.landsIn) ?? null,
  }
}

/** The primary output the asset defines, or null when it defines none. */
export function templateOutput(
  asset: Pick<MarketplaceAssetDetail, "config" | "title">,
): TemplateOutput | null {
  const config = isRow(asset.config) ? asset.config : undefined
  if (!config) return null
  const fallbackTitle = asset.title
  const listed = config.outputs ?? config.deliverables
  if (Array.isArray(listed)) {
    for (const item of listed) {
      const output = normaliseOutput(item, fallbackTitle)
      if (output) return output
    }
  }
  const single =
    config.output ?? config.deliverable ?? config.sampleOutput ?? config.sample_output
  return normaliseOutput(single, fallbackTitle)
}

export function isReportOutput(output: TemplateOutput): boolean {
  const haystack = `${output.kind ?? ""} ${output.title} ${output.destination ?? ""}`.toLowerCase()
  return /\b(report|reports|digest|summary|brief|dashboard)\b/.test(haystack)
}

const CADENCE_LABEL: Record<string, string> = {
  hourly: "Runs hourly",
  daily: "Runs daily",
  weekdays: "Runs on weekdays",
  weekly: "Runs weekly",
  biweekly: "Runs every two weeks",
  fortnightly: "Runs every two weeks",
  monthly: "Runs monthly",
  quarterly: "Runs quarterly",
  manual: "Runs on demand",
  on_demand: "Runs on demand",
  ondemand: "Runs on demand",
  event: "Runs on events",
  webhook: "Runs on events",
  trigger: "Runs on events",
}

function cadenceFrom(value: unknown): string | null {
  const asText = text(value)
  if (asText) {
    const key = asText.toLowerCase().replace(/[\s-]+/g, "_")
    if (CADENCE_LABEL[key]) return CADENCE_LABEL[key]
    // A cron expression or other schedule string: honest, not specific.
    if (/^[\d*/,\-\s?LW#]+$/i.test(asText) || asText.split(/\s+/).length >= 5) return "Runs on a schedule"
    return null
  }
  if (!isRow(value)) return null
  return (
    cadenceFrom(value.cadence) ??
    cadenceFrom(value.frequency) ??
    cadenceFrom(value.interval) ??
    cadenceFrom(value.cron) ??
    (String(value.type ?? "").toLowerCase() === "schedule" ? "Runs on a schedule" : null) ??
    cadenceFrom(value.type)
  )
}

/** "Runs weekly" style label from the definition, or null when it does not say. */
export function templateCadence(asset: Pick<MarketplaceAssetDetail, "config">): string | null {
  const config = isRow(asset.config) ? asset.config : undefined
  if (!config) return null
  return (
    cadenceFrom(config.cadence) ??
    cadenceFrom(config.schedule) ??
    cadenceFrom(config.frequency) ??
    cadenceFrom(config.trigger) ??
    null
  )
}

/** Pill copy for required apps, or null when the checklist was not reported. */
export function requiredAppsLabel(
  asset: Pick<MarketplaceAssetDetail, "connectorChecklist">,
): string | null {
  if (!Array.isArray(asset.connectorChecklist)) return null
  const required = asset.connectorChecklist.filter((item) => item.required).length
  if (required === 0) return "No required apps"
  return `${required} required app${required === 1 ? "" : "s"}`
}

export const MARKETPLACE_TYPE_LABEL: Record<string, string> = {
  ai_agent: "Agent",
  workflow: "Workflow",
  knowledge_pack: "Knowledge pack",
  department_pack: "Department pack",
  intelligence_pack: "Intelligence pack",
  connector_config: "Connector",
  play: "Play",
  outcome_pack: "Outcome pack",
  dataset_pack: "Dataset",
  dashboard_pack: "Dashboard",
  capability_package: "Skill or plugin",
}

export function marketplaceTypeLabel(assetType: string): string {
  return MARKETPLACE_TYPE_LABEL[assetType] ?? humanise(assetType)
}

export interface PipelineFitStage {
  stageId: string
  label: string
  /** True when this template is listed for the stage or calls one of its tools. */
  matched: boolean
}

/**
 * Stages of the department pipeline with the ones this template serves marked:
 * a stage matches when it lists the asset's slug among its marketplace packs or
 * references a tool action one of the template's steps calls.
 */
export function pipelineFitStages(
  pipeline: unknown,
  asset: Pick<MarketplaceAssetDetail, "slug">,
  steps: TemplateStep[],
): PipelineFitStage[] {
  if (!isRow(pipeline)) return []
  const specs = Array.isArray(pipeline.stages) ? pipeline.stages.filter(isRow) : []
  const statuses = Array.isArray(pipeline.stageStatuses) ? pipeline.stageStatuses.filter(isRow) : []
  const rows = specs.length > 0 ? specs : statuses
  const tools = new Set(
    steps.map((step) => step.tool?.toLowerCase()).filter((tool): tool is string => Boolean(tool)),
  )
  return rows
    .map((row) => {
      const stageId = text(row.stageId) ?? ""
      const label = text(row.label) ?? humanise(stageId)
      const packs = Array.isArray(row.marketplacePackIds) ? row.marketplacePackIds.map(String) : []
      const refs = Array.isArray(row.references)
        ? row.references.map((ref) => String(ref).toLowerCase())
        : []
      const matched = packs.includes(asset.slug) || refs.some((ref) => tools.has(ref))
      return { stageId, label, matched }
    })
    .filter((stage) => Boolean(stage.label))
}

const ACRONYMS = new Set(["hr", "it", "msp", "cs", "ai", "seo", "crm", "gtm"])

/** "Revenue Operations" from "revenue_operations" / "Revenue Operations". */
export function departmentLabel(department: string | null | undefined): string | null {
  const value = text(department)
  if (!value) return null
  if (/[A-Z]/.test(value)) return value.replace(/_/g, " ")
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => (ACRONYMS.has(word.toLowerCase()) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(" ")
}
