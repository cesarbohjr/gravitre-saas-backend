import type { MlModelType } from "@/types/api"

export type MlStackLayerId =
  | "generative"
  | "classical"
  | "timeseries"
  | "anomaly"
  | "mlops"

export interface MlStackLayer {
  id: MlStackLayerId
  title: string
  summary: string
  highlights: string[]
  accent: string
}

export interface ModelTypeMeta {
  value: MlModelType
  label: string
  tagline: string
  layer: MlStackLayerId
  examples: string[]
}

export type BaseModelAvailability = "platform" | "connected" | "requires_connection"

export interface BaseModelOption {
  id: string
  label: string
  description: string
  provider: string
  layer: MlStackLayerId
  availability: BaseModelAvailability
  /** Connector vendor key when availability is tied to an integration */
  connectorVendor?: string
  recommended?: boolean
  /** Provider API model id (same as id when omitted) */
  apiModelId?: string
  /** Short version or release tag shown in UI */
  versionTag?: string
  /** Whether provider supports fine-tuning on this base (registry hint only) */
  fineTunable?: boolean
}

export interface MlRegistryTemplate {
  layerId: MlStackLayerId
  modelType: MlModelType
  name: string
  description: string
  taskType: string
  /** Prefer this base when available; falls back to type default */
  preferredBaseModelId?: string
}

export const ML_STACK_LAYERS: MlStackLayer[] = [
  {
    id: "generative",
    title: "Assistants & agents",
    summary: "Teach a language model your tone, policies, and tool habits.",
    highlights: ["Brand voice", "Agent tool use", "Quality checks"],
    accent: "from-emerald-500/20 to-teal-500/10 ring-emerald-500/20",
  },
  {
    id: "classical",
    title: "Scoring & classification",
    summary: "Predict categories from CRM, billing, and ops data.",
    highlights: ["Lead scoring", "Churn risk", "Ticket routing"],
    accent: "from-sky-500/20 to-blue-500/10 ring-sky-500/20",
  },
  {
    id: "timeseries",
    title: "Forecasting",
    summary: "Project demand, capacity, and revenue ahead of time.",
    highlights: ["Seasonal forecasts", "Revenue outlook", "Backtesting"],
    accent: "from-amber-500/20 to-orange-500/10 ring-amber-500/20",
  },
  {
    id: "anomaly",
    title: "Anomaly detection",
    summary: "Catch fraud spikes, drift, and infra incidents early.",
    highlights: ["Unusual patterns", "Live scores", "Alert thresholds"],
    accent: "from-rose-500/20 to-red-500/10 ring-rose-500/20",
  },
  {
    id: "mlops",
    title: "Deploy & monitor",
    summary: "Version models, put them in workflows, and watch latency.",
    highlights: ["Version history", "Workflow calls", "Rollback"],
    accent: "from-emerald-500/20 to-teal-500/10 ring-emerald-500/20",
  },
]

export const MODEL_TYPE_CATALOG: ModelTypeMeta[] = [
  {
    value: "fine_tuned_llm",
    label: "Fine-tuned LLM",
    tagline: "Adapt a foundation model to your org voice and tasks.",
    layer: "generative",
    examples: ["Support copilot", "SDR email drafts", "Policy Q&A"],
  },
  {
    value: "classifier",
    label: "Classifier",
    tagline: "Predict categories from structured features.",
    layer: "classical",
    examples: ["Lead grade", "Ticket priority", "Fraud label"],
  },
  {
    value: "forecaster",
    label: "Forecaster",
    tagline: "Project metrics forward with seasonality.",
    layer: "timeseries",
    examples: ["Revenue forecast", "Ticket volume", "Inventory"],
  },
  {
    value: "anomaly_detector",
    label: "Anomaly detector",
    tagline: "Flag unusual patterns in metrics or events.",
    layer: "anomaly",
    examples: ["Payment spikes", "API error bursts", "Usage drift"],
  },
]

/** Starting templates when clicking a stack-layer card on the registry overview */
export const ML_REGISTRY_TEMPLATES: Record<MlStackLayerId, MlRegistryTemplate> = {
  generative: {
    layerId: "generative",
    modelType: "fine_tuned_llm",
    name: "Support copilot",
    description: "Fine-tuned assistant for customer support tone, policies, and tool routing.",
    taskType: "instruction_tuning",
    preferredBaseModelId: "gpt-4.1-mini",
  },
  classical: {
    layerId: "classical",
    modelType: "classifier",
    name: "Lead scoring classifier",
    description: "Scores inbound leads for sales routing from CRM and product usage features.",
    taskType: "binary",
    preferredBaseModelId: "xgboost",
  },
  timeseries: {
    layerId: "timeseries",
    modelType: "forecaster",
    name: "Revenue forecaster",
    description: "Projects weekly revenue with seasonality and holiday effects.",
    taskType: "weekly",
    preferredBaseModelId: "forecaster",
  },
  anomaly: {
    layerId: "anomaly",
    modelType: "anomaly_detector",
    name: "API anomaly detector",
    description: "Flags unusual error rates, latency spikes, and traffic patterns.",
    taskType: "point",
    preferredBaseModelId: "isolation-forest",
  },
  mlops: {
    layerId: "mlops",
    modelType: "fine_tuned_llm",
    name: "Workflow inference model",
    description: "Deployable LLM version for Meson nodes and agent tool calls.",
    taskType: "tool_use",
    preferredBaseModelId: "gpt-4.1",
  },
}

const LLM_BASE_MODELS: BaseModelOption[] = [
  // OpenAI (ChatGPT)
  {
    id: "gpt-6-astra",
    label: "GPT-6 Astra",
    versionTag: "flagship",
    description: "OpenAI flagship for complex reasoning and agent workflows.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    recommended: true,
    fineTunable: false,
  },
  {
    id: "gpt-6.1-sol",
    label: "GPT-6.1 Sol",
    versionTag: "balanced",
    description: "Near-flagship OpenAI quality at a fraction of the cost.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gpt-6-luna",
    label: "GPT-6 Luna",
    versionTag: "fast",
    description: "Fast, low-cost OpenAI model for high-volume inference.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gpt-4.1",
    label: "GPT-4.1",
    versionTag: "fine-tunable",
    description: "OpenAI base supported for fine-tuning (SFT/DPO).",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: true,
  },
  {
    id: "gpt-4.1-mini",
    label: "GPT-4.1 Mini",
    versionTag: "fine-tunable",
    description: "Cost-efficient OpenAI base supported for fine-tuning (SFT/DPO).",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: true,
  },
  // Anthropic (Claude)
  {
    id: "claude-fable-5-1",
    label: "Claude Fable 5.1",
    versionTag: "flagship",
    description: "Anthropic's most capable model for the hardest long-horizon work.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "claude-opus-5-5",
    label: "Claude Opus 5.5",
    versionTag: "5.5",
    description: "Frontier Claude for deep reasoning, coding, and agents.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    recommended: true,
    fineTunable: false,
  },
  {
    id: "claude-sonnet-5-5",
    label: "Claude Sonnet 5.5",
    versionTag: "5.5",
    description: "Balanced Claude for writing, coding, and everyday agent work.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "claude-haiku-4-5",
    label: "Claude Haiku 4.5",
    versionTag: "fast",
    description: "Fastest Claude for routing, triage, and high-QPS agents.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  // Google (Gemini)
  {
    id: "gemini-3.1-pro-preview",
    label: "Gemini 3.1 Pro",
    versionTag: "preview",
    description: "Google's most capable Gemini for long context and rich media.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gemini-3.8-flash",
    label: "Gemini 3.8 Flash",
    versionTag: "3.8",
    description: "Most intelligent Gemini Flash for agent loops and tool use.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gemini-3.5-flash-lite",
    label: "Gemini 3.5 Flash-Lite",
    versionTag: "fast",
    description: "Fast, low-cost Gemini for summarization and extraction.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gemini-3.1-flash-lite",
    label: "Gemini 3.1 Flash-Lite",
    versionTag: "cheapest",
    description: "Cheapest Gemini for bulk classification work.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
]

// Base ids below must be trainable by backend/app/workers/training_worker.py
// (directly or via its MODEL_BASE_ALIASES), otherwise training jobs fail.
const CLASSIFIER_BASE_MODELS: BaseModelOption[] = [
  {
    id: "success_predictor",
    label: "Outcome predictor",
    versionTag: "Gravitre",
    description: "Binary success/failure model that returns an outcome probability.",
    provider: "Gravitre",
    layer: "classical",
    availability: "platform",
  },
  {
    id: "xgboost",
    label: "XGBoost",
    versionTag: "2.x",
    description: "Gradient-boosted trees. Industry standard for tabular classification.",
    provider: "XGBoost",
    layer: "classical",
    availability: "connected",
    connectorVendor: "postgresql",
    recommended: true,
  },
  {
    id: "gradient_boosting",
    label: "Gradient boosting",
    versionTag: "sklearn",
    description: "Boosted trees without extra dependencies; good on skewed scoring data.",
    provider: "scikit-learn",
    layer: "classical",
    availability: "platform",
  },
  {
    id: "random-forest",
    label: "Random forest",
    versionTag: "sklearn",
    description: "Interpretable ensemble baseline with feature importance.",
    provider: "scikit-learn",
    layer: "classical",
    availability: "connected",
    connectorVendor: "segment",
  },
  {
    id: "logistic-regression",
    label: "Logistic regression",
    versionTag: "sklearn",
    description: "Simple, auditable linear classifier for regulated use cases.",
    provider: "scikit-learn",
    layer: "classical",
    availability: "platform",
  },
]

const FORECASTER_BASE_MODELS: BaseModelOption[] = [
  {
    id: "forecaster",
    label: "Metric forecaster",
    versionTag: "Gravitre",
    description: "Gradient-boosted regressor that projects business metrics forward.",
    provider: "Gravitre",
    layer: "timeseries",
    availability: "platform",
    recommended: true,
  },
]

const ANOMALY_BASE_MODELS: BaseModelOption[] = [
  {
    id: "isolation-forest",
    label: "Isolation forest",
    description: "Fast multivariate outlier detection.",
    provider: "scikit-learn",
    layer: "anomaly",
    availability: "connected",
    connectorVendor: "postgresql",
    recommended: true,
  },
]

const DATA_CONNECTOR_VENDORS = new Set([
  "postgresql",
  "snowflake",
  "mongodb",
  "segment",
  "hubspot",
  "salesforce",
  "stripe",
  "google_sheets",
])

export function resolveBaseModelOptions(
  modelType: MlModelType,
  connectedVendorKeys: Set<string>
): BaseModelOption[] {
  let options: BaseModelOption[]
  switch (modelType) {
    case "fine_tuned_llm":
      options = LLM_BASE_MODELS
      break
    case "classifier":
      options = CLASSIFIER_BASE_MODELS
      break
    case "forecaster":
      options = FORECASTER_BASE_MODELS
      break
    case "anomaly_detector":
      options = ANOMALY_BASE_MODELS
      break
    default:
      options = []
  }

  return options.map((option) => {
    if (option.availability === "platform") return option
    const vendor = option.connectorVendor
    if (!vendor) return option
    const connected =
      connectedVendorKeys.has(vendor) ||
      (vendor === "postgresql" && connectedVendorKeys.has("mongodb"))
    return {
      ...option,
      availability: connected ? "connected" : "requires_connection",
    }
  })
}

export function defaultBaseModelForType(
  modelType: MlModelType,
  connectedVendorKeys: Set<string>
): string {
  const options = resolveBaseModelOptions(modelType, connectedVendorKeys)
  const pick = options.find((o) => o.recommended && o.availability !== "requires_connection")
    ?? options.find((o) => o.availability !== "requires_connection")
    ?? options[0]
  return pick?.id ?? ""
}

/** Use `preferredId` when it is offered and usable; otherwise the type default. */
export function preferredBaseModelForType(
  modelType: MlModelType,
  preferredId: string | null | undefined,
  connectedVendorKeys: Set<string>
): string {
  const preferred = preferredId
    ? resolveBaseModelOptions(modelType, connectedVendorKeys).find((o) => o.id === preferredId)
    : undefined
  if (preferred && preferred.availability !== "requires_connection") return preferred.id
  return defaultBaseModelForType(modelType, connectedVendorKeys)
}

export function templateForLayer(layerId: MlStackLayerId): MlRegistryTemplate {
  return ML_REGISTRY_TEMPLATES[layerId]
}

export function applyRegistryTemplate(
  template: MlRegistryTemplate,
  connectedVendorKeys: Set<string>
): {
  modelType: MlModelType
  name: string
  description: string
  taskType: string
  baseModel: string
} {
  const baseModel = preferredBaseModelForType(
    template.modelType,
    template.preferredBaseModelId,
    connectedVendorKeys
  )

  return {
    modelType: template.modelType,
    name: template.name,
    description: template.description,
    taskType: template.taskType,
    baseModel,
  }
}

export function modelTypeMeta(modelType: MlModelType): ModelTypeMeta | undefined {
  return MODEL_TYPE_CATALOG.find((m) => m.value === modelType)
}

export function layerForModelType(modelType: MlModelType): MlStackLayerId {
  return modelTypeMeta(modelType)?.layer ?? "mlops"
}

export function connectedDataSources(vendors: Set<string>): string[] {
  return [...vendors].filter((v) => DATA_CONNECTOR_VENDORS.has(v))
}

export const TASK_TYPE_SUGGESTIONS: Record<MlModelType, string[]> = {
  fine_tuned_llm: ["instruction_tuning", "tool_use", "classification", "summarization"],
  classifier: ["binary", "multiclass", "ranking"],
  forecaster: ["daily", "weekly", "hourly"],
  anomaly_detector: ["point", "contextual", "collective"],
}

export const ML_LIFECYCLE_STEPS = [
  { id: "draft", label: "Register", detail: "Capture type, base model, and task profile." },
  { id: "training", label: "Train", detail: "Run a job on Training with linked dataset." },
  { id: "validating", label: "Validate", detail: "Review metrics and holdout performance." },
  { id: "ready", label: "Ready", detail: "Artifact stored; eligible for deployment." },
  { id: "deployed", label: "Deploy", detail: "Serve inference to workflows and agents." },
] as const

export interface MlTrainingGuidance {
  headline: string
  bullets: string[]
  datasetHint: string
  evalMetrics: string[]
}

export const ML_TRAINING_GUIDANCE: Record<MlModelType, MlTrainingGuidance> = {
  fine_tuned_llm: {
    headline: "Instruction tuning for domain-specific assistants",
    bullets: [
      "Use JSONL with system + user + assistant message turns.",
      "OpenAI fine-tuning supports gpt-4.1, gpt-4.1-mini, and o4-mini; GPT-5 and Claude/Gemini/Grok bases are inference-first.",
      "Pick the provider API id (e.g. claude-sonnet-4-6, gemini-2.5-pro, grok-3) to align registry metadata with production routing.",
    ],
    datasetHint: "Upload conversational JSONL on Training with clear system prompts.",
    evalMetrics: ["loss", "token_accuracy", "human_eval"],
  },
  classifier: {
    headline: "Tabular classification on CRM or ops features",
    bullets: [
      "Normalize numeric features; encode categoricals before export.",
      "XGBoost and gradient boosting excel on skewed lead-scoring data.",
      "Watch class imbalance. Prefer stratified splits and F1 over accuracy alone.",
    ],
    datasetHint: "Export labeled rows from PostgreSQL, Snowflake, or Segment.",
    evalMetrics: ["accuracy", "f1", "roc_auc", "precision", "recall"],
  },
  forecaster: {
    headline: "Time-series projection with seasonality",
    bullets: [
      "Include timestamp + target columns with a consistent granularity.",
      "Add calendar features (weekday, month, holiday flags) to capture seasonality.",
      "Backtest on rolling windows before deploying to workflows.",
    ],
    datasetHint: "Daily or hourly metric series with consistent granularity.",
    evalMetrics: ["mape", "rmse", "mae", "coverage"],
  },
  anomaly_detector: {
    headline: "Multivariate outlier detection for metrics and events",
    bullets: [
      "Isolation forest is fast for high-volume API or payment streams.",
      "Tune contamination rate to expected anomaly frequency.",
      "Pair scores with alert thresholds in workflow nodes.",
    ],
    datasetHint: "Unlabeled metric snapshots or event feature vectors.",
    evalMetrics: ["precision_at_k", "recall", "f1"],
  },
}

export function stackLayerById(id: MlStackLayerId): MlStackLayer | undefined {
  return ML_STACK_LAYERS.find((layer) => layer.id === id)
}

export function lookupBaseModelOption(
  modelType: MlModelType,
  baseModelId: string | null | undefined,
  connectedVendorKeys: Set<string>
): BaseModelOption | undefined {
  if (!baseModelId) return undefined
  return resolveBaseModelOptions(modelType, connectedVendorKeys).find((o) => o.id === baseModelId)
}

export function inferenceSampleInputs(modelType: MlModelType): Record<string, unknown>[] {
  switch (modelType) {
    case "fine_tuned_llm":
      return [
        {
          messages: [{ role: "user", content: "Score this lead: Series B fintech, 50 employees, inbound demo request." }],
          temperature: 0.3,
          max_tokens: 200,
        },
      ]
    case "classifier":
      return [{ company_size: 50, industry_score: 0.8, inbound: 1, demo_requested: 1 }]
    case "forecaster":
      return [{ step_count: 5, connector_count: 2, decision_count: 1, avg_duration_ms: 4200 }]
    case "anomaly_detector":
      return [{ error_rate: 0.12, latency_p99_ms: 890, request_volume: 15000 }]
    default:
      return [{}]
  }
}

export function lifecycleStepIndex(status: string): number {
  const order = ML_LIFECYCLE_STEPS.map((s) => s.id)
  const idx = order.indexOf(status as (typeof order)[number])
  if (idx >= 0) return idx
  if (status === "failed" || status === "archived") return 1
  return 0
}
