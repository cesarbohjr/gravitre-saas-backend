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
    title: "Generative & agents",
    summary: "Fine-tune LLMs for domain tone, tools, and workflow agents.",
    highlights: ["RLHF / instruction tuning", "Agent tool routing", "Eval + guardrails"],
    accent: "from-violet-500/20 to-fuchsia-500/10 ring-violet-500/20",
  },
  {
    id: "classical",
    title: "Tabular & classification",
    summary: "Gradient-boosted and linear models on CRM, billing, and ops data.",
    highlights: ["Lead scoring", "Churn prediction", "Routing classifiers"],
    accent: "from-blue-500/20 to-cyan-500/10 ring-blue-500/20",
  },
  {
    id: "timeseries",
    title: "Forecasting",
    summary: "Seasonal demand, capacity, and revenue projections.",
    highlights: ["Prophet & neural TS", "Foundation time-series models", "Backtesting"],
    accent: "from-amber-500/20 to-orange-500/10 ring-amber-500/20",
  },
  {
    id: "anomaly",
    title: "Anomaly detection",
    summary: "Spot drift, fraud spikes, and infra incidents early.",
    highlights: ["Multivariate outliers", "Streaming scores", "Alert thresholds"],
    accent: "from-rose-500/20 to-red-500/10 ring-rose-500/20",
  },
  {
    id: "mlops",
    title: "MLOps & deployment",
    summary: "Version artifacts, deploy to workflows, and monitor latency.",
    highlights: ["Registry versions", "Workflow inference nodes", "Rollback"],
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
    preferredBaseModelId: "prophet",
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
    id: "gpt-5.5",
    label: "GPT-5.5",
    versionTag: "flagship",
    description: "Latest OpenAI flagship for complex reasoning and agent workflows.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    recommended: true,
    fineTunable: false,
  },
  {
    id: "gpt-5.4-mini",
    label: "GPT-5.4 Mini",
    versionTag: "fast",
    description: "Low-latency ChatGPT model for high-volume inference.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gpt-4.1",
    label: "GPT-4.1",
    versionTag: "2025-04",
    description: "Production-grade ChatGPT base; strong tool use and instruction following.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: true,
  },
  {
    id: "gpt-4.1-mini",
    label: "GPT-4.1 Mini",
    versionTag: "2025-04",
    description: "Cost-efficient OpenAI base; supported for fine-tuning (SFT/DPO).",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: true,
  },
  {
    id: "gpt-4o",
    label: "GPT-4o",
    versionTag: "2024-08",
    description: "Omni multimodal ChatGPT model for text + vision workloads.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o Mini",
    versionTag: "2024-07",
    description: "Affordable GPT-4o variant for classification and extraction tasks.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "o3-mini",
    label: "o3-mini",
    versionTag: "reasoning",
    description: "OpenAI reasoning model for multi-step analysis (inference only).",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "o4-mini",
    label: "o4-mini",
    versionTag: "2025-04",
    description: "Compact reasoning model; OpenAI supports RFT fine-tuning on this base.",
    provider: "OpenAI",
    layer: "generative",
    availability: "platform",
    fineTunable: true,
  },
  // Anthropic (Claude)
  {
    id: "claude-sonnet-4-6",
    label: "Claude Sonnet 4.6",
    versionTag: "4.6",
    description: "Balanced Claude model for writing, coding, and agent orchestration.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    recommended: true,
    fineTunable: false,
  },
  {
    id: "claude-haiku-4-5-20251001",
    label: "Claude Haiku 4.5",
    versionTag: "4.5 · 2025-10-01",
    description: "Fastest Claude tier for routing, triage, and high-QPS agents.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "claude-opus-4-6",
    label: "Claude Opus 4.6",
    versionTag: "4.6",
    description: "Highest-capability Claude for deep research and complex workflows.",
    provider: "Anthropic",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  // Google (Gemini)
  {
    id: "gemini-2.5-pro",
    label: "Gemini 2.5 Pro",
    versionTag: "2.5",
    description: "Google flagship multimodal model for long context and rich media.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gemini-2.5-flash",
    label: "Gemini 2.5 Flash",
    versionTag: "2.5",
    description: "Fast Gemini tier for agent loops, summarization, and tool use.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    versionTag: "2.0",
    description: "Stable flash model for cost-sensitive production workloads.",
    provider: "Google",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  // xAI (Grok)
  {
    id: "grok-3",
    label: "Grok 3",
    versionTag: "3",
    description: "xAI flagship model for real-time knowledge and conversational agents.",
    provider: "xAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "grok-3-mini",
    label: "Grok 3 Mini",
    versionTag: "3 mini",
    description: "Efficient Grok variant for high-throughput inference.",
    provider: "xAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
  {
    id: "grok-2-1212",
    label: "Grok 2",
    versionTag: "2 · 2024-12-12",
    description: "Previous-generation Grok base (grok-2-1212 API id).",
    provider: "xAI",
    layer: "generative",
    availability: "platform",
    fineTunable: false,
  },
]

const CLASSIFIER_BASE_MODELS: BaseModelOption[] = [
  {
    id: "xgboost",
    label: "XGBoost",
    versionTag: "2.x",
    description: "Gradient-boosted trees — industry standard for tabular classification.",
    provider: "XGBoost",
    layer: "classical",
    availability: "connected",
    connectorVendor: "postgresql",
    recommended: true,
  },
  {
    id: "lightgbm",
    label: "LightGBM",
    versionTag: "4.x",
    description: "Fast training on wide feature sets and large categoricals.",
    provider: "Microsoft",
    layer: "classical",
    availability: "connected",
    connectorVendor: "postgresql",
  },
  {
    id: "catboost",
    label: "CatBoost",
    versionTag: "1.2",
    description: "Handles high-cardinality categoricals without heavy encoding.",
    provider: "Yandex",
    layer: "classical",
    availability: "connected",
    connectorVendor: "snowflake",
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
    id: "prophet",
    label: "Prophet",
    description: "Robust seasonality for business metrics.",
    provider: "Meta",
    layer: "timeseries",
    availability: "connected",
    connectorVendor: "postgresql",
    recommended: true,
  },
  {
    id: "neuralprophet",
    label: "NeuralProphet",
    description: "Neural extension of Prophet for complex seasonality.",
    provider: "Open source",
    layer: "timeseries",
    availability: "connected",
    connectorVendor: "postgresql",
  },
  {
    id: "statsforecast-arima",
    label: "StatsForecast ARIMA",
    description: "Classical statistical forecasting baseline.",
    provider: "Nixtla",
    layer: "timeseries",
    availability: "platform",
  },
  {
    id: "chronos-bolt-base",
    label: "Chronos Bolt",
    versionTag: "Amazon",
    description: "Foundation time-series model (zero-shot baseline + fine-tune).",
    provider: "Amazon",
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
  {
    id: "autoencoder",
    label: "Deep autoencoder",
    versionTag: "PyTorch",
    description: "Neural reconstruction error for complex multivariate patterns.",
    provider: "PyTorch",
    layer: "anomaly",
    availability: "connected",
    connectorVendor: "snowflake",
  },
  {
    id: "merlion",
    label: "Merlion",
    versionTag: "Salesforce",
    description: "Unified anomaly detection and forecasting toolkit.",
    provider: "Salesforce",
    layer: "anomaly",
    availability: "platform",
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
  const options = resolveBaseModelOptions(template.modelType, connectedVendorKeys)
  const preferred = template.preferredBaseModelId
    ? options.find((o) => o.id === template.preferredBaseModelId)
    : undefined
  const baseModel =
    (preferred && preferred.availability !== "requires_connection" ? preferred.id : undefined)
    ?? defaultBaseModelForType(template.modelType, connectedVendorKeys)

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
      "XGBoost and LightGBM excel on skewed lead-scoring data.",
      "Watch class imbalance — use stratified splits and F1, not accuracy alone.",
    ],
    datasetHint: "Export labeled rows from PostgreSQL, Snowflake, or Segment.",
    evalMetrics: ["accuracy", "f1", "roc_auc", "precision", "recall"],
  },
  forecaster: {
    headline: "Time-series projection with seasonality",
    bullets: [
      "Include timestamp + target columns; Prophet handles holidays automatically.",
      "Backtest on rolling windows before deploying to workflows.",
      "Chronos Bolt supports zero-shot baselines when labeled history is thin.",
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
