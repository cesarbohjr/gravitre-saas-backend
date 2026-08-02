/**
 * Novice-friendly metadata for GIBE built-in catalog models.
 * Technical ids stay as keys; UI should prefer label / summary / whyItMatters.
 */

export type BuiltInModelDomainId =
  | "customer"
  | "workflows"
  | "search"
  | "revenue"
  | "support"
  | "learning"
  | "future"

export type BuiltInModelDomain = {
  id: BuiltInModelDomainId
  title: string
  summary: string
  order: number
}

export type BuiltInModelGuide = {
  id: string
  label: string
  summary: string
  /** Why training this model with org data matters */
  whyItMatters: string
  /** What the data bar means in plain English */
  dataExplainer: string
  domain: BuiltInModelDomainId
  /** How users grow the signal count */
  howToFeed?: string
}

export const BUILT_IN_MODEL_DOMAINS: BuiltInModelDomain[] = [
  {
    id: "customer",
    title: "Customers & deals",
    summary: "Spot churn risk, recommend next actions, and score deal outcomes.",
    order: 1,
  },
  {
    id: "workflows",
    title: "Workflows & ops",
    summary: "Predict run risk, duration, and capacity before work piles up.",
    order: 2,
  },
  {
    id: "search",
    title: "Search & knowledge",
    summary: "Improve answers, ranking, and what the org remembers.",
    order: 3,
  },
  {
    id: "revenue",
    title: "Revenue",
    summary: "Forecast revenue from CRM and finance signals.",
    order: 4,
  },
  {
    id: "support",
    title: "Support",
    summary: "Anticipate SLA risk and ticket volume.",
    order: 5,
  },
  {
    id: "learning",
    title: "Learning engine",
    summary: "Route questions and improve how Gravitre learns from usage.",
    order: 6,
  },
  {
    id: "future",
    title: "Coming capabilities",
    summary: "Platform roadmap models — not trainable in your org yet.",
    order: 7,
  },
]

const GUIDES: BuiltInModelGuide[] = [
  {
    id: "intent_classifier",
    label: "Question router",
    summary: "Figures out what someone is asking so the right tools and departments respond.",
    whyItMatters:
      "Without enough labeled questions, Gravitre guesses intent with rules. Training makes routing match how your org actually talks.",
    dataExplainer: "Needs enough labeled chat/query examples before org-specific training is reliable.",
    domain: "learning",
    howToFeed: "Keep using chat and workflows — labeled query history fills this automatically.",
  },
  {
    id: "workflow_anomaly_detector",
    label: "Workflow anomaly detector",
    summary: "Flags unusual workflow behavior that may mean a bottleneck or failure pattern.",
    whyItMatters: "Early warnings beat firefighting. More completed runs teach what “normal” looks like for your org.",
    dataExplainer: "Needs a baseline of workflow runs before anomalies can be distinguished from noise.",
    domain: "workflows",
    howToFeed: "Run production workflows regularly so history accumulates.",
  },
  {
    id: "workflow_duration_forecaster",
    label: "Run duration forecaster",
    summary: "Estimates how long a workflow will take based on similar past runs.",
    whyItMatters: "Helps schedule work and set expectations instead of guessing from averages alone.",
    dataExplainer: "Needs enough historical runs with durations to forecast confidently.",
    domain: "workflows",
  },
  {
    id: "workflow_success_predictor",
    label: "Run success predictor",
    summary: "Scores the chance a workflow will succeed before or during execution.",
    whyItMatters: "Lets operators intervene on risky runs earlier — advisory, not auto-blocking.",
    dataExplainer: "Needs enough completed runs (success and failure) to learn risk patterns.",
    domain: "workflows",
  },
  {
    id: "retrieval_ranker",
    label: "Answer quality ranker",
    summary: "Orders knowledge chunks so the most helpful sources surface first in RAG answers.",
    whyItMatters: "Better ranking means fewer wrong or vague answers from your knowledge base.",
    dataExplainer: "Needs evaluated responses / chunk feedback before org ranking beats the default.",
    domain: "search",
    howToFeed: "Rate or approve assistant answers; helpfulness outcomes train this model.",
  },
  {
    id: "query_clusterer",
    label: "Topic cluster finder",
    summary: "Groups recurring questions to reveal knowledge gaps and themes.",
    whyItMatters: "Shows what people keep asking — so you know what docs or agents to improve.",
    dataExplainer: "Needs a variety of distinct queries before clusters are meaningful.",
    domain: "search",
  },
  {
    id: "memory_promotion_scorer",
    label: "Memory promotion scorer",
    summary: "Prioritizes which memories should be promoted into durable org knowledge.",
    whyItMatters: "Stops noise from becoming “truth” while surfacing high-value facts faster.",
    dataExplainer: "Needs resolved promotion decisions (approve/reject history).",
    domain: "search",
  },
  {
    id: "retrieval_memory_learner",
    label: "Unified retrieval learner",
    summary: "Combines retrieval and memory signals so search quality improves over time.",
    whyItMatters: "Keeps chat grounded in what worked for your org, not only generic ranking.",
    dataExplainer: "Improves as retrieval and memory outcomes accumulate across learning versions.",
    domain: "search",
  },
  {
    id: "revenue_forecaster",
    label: "Revenue forecaster",
    summary: "Projects near-term revenue from CRM and finance connector history.",
    whyItMatters: "Gives planning a data-backed outlook instead of spreadsheet gut feel.",
    dataExplainer: "Needs enough dated revenue points from connected finance/CRM sources.",
    domain: "revenue",
    howToFeed: "Connect CRM/finance sources and keep deals and invoices syncing.",
  },
  {
    id: "churn_risk_scorer",
    label: "Customer churn risk",
    summary: "Scores which customers look likely to cancel or not renew — advisory only.",
    whyItMatters: "Gives CS and account teams time to intervene before revenue walks out.",
    dataExplainer: "Needs labeled customer risk signals (cancel, non-renew, closed-lost outcomes).",
    domain: "customer",
    howToFeed: "Connect CRM/CS tools and keep churn outcomes labeled in your data.",
  },
  {
    id: "cf_matrix_factorizer",
    label: "Smart recommendations",
    summary: "Soft-ranks next actions or items from how people in your org interact.",
    whyItMatters: "Surfaces what similar users found useful — without hard-coding rules for every case.",
    dataExplainer: "Needs enough recent scored interactions across multiple people and items.",
    domain: "customer",
  },
  {
    id: "sla_breach_predictor",
    label: "SLA breach risk",
    summary: "Predicts which support tickets are heading toward an SLA miss.",
    whyItMatters: "Lets support rebalance queue load before customers feel the breach.",
    dataExplainer: "Needs tickets with SLA resolution timestamps from your support stack.",
    domain: "support",
    howToFeed: "Connect your helpdesk and keep SLA fields populated.",
  },
  {
    id: "deal_loss_scorer",
    label: "Deal loss risk",
    summary: "Estimates probability a CRM deal will be lost based on measured outcomes.",
    whyItMatters: "Focuses sellers on at-risk pipeline instead of every open opportunity equally.",
    dataExplainer: "Needs enough closed-won / closed-lost deals with measured outcomes.",
    domain: "customer",
  },
  {
    id: "capacity_forecaster",
    label: "Support capacity forecast",
    summary: "Forecasts support ticket volume so staffing can match demand.",
    whyItMatters: "Avoids understaffed spikes and idle overstaffing.",
    dataExplainer: "Needs daily ticket volume history from your support tools.",
    domain: "support",
  },
  {
    id: "causal_impact_analyzer",
    label: "Cause & effect analyzer",
    summary: "Estimates whether an action actually moved a business metric (not just correlation).",
    whyItMatters: "Stops teams from celebrating coincidences as strategy wins.",
    dataExplainer: "Needs before/after observations for the same metric around real actions.",
    domain: "future",
  },
  {
    id: "graph_neural_network",
    label: "Relationship graph scorer",
    summary: "Scores entity relationships across your knowledge graph at larger scale.",
    whyItMatters: "Helps discover non-obvious links between people, accounts, and knowledge.",
    dataExplainer: "Requires a large relationship graph and specialized compute — platform gated.",
    domain: "future",
  },
  {
    id: "multimodal_router",
    label: "Image & document router",
    summary: "Routes image and document tasks to the right vision-capable path.",
    whyItMatters: "Lets workflows handle attachments without forcing everything through text-only models.",
    dataExplainer: "Activates with vision-capable model routing — partially available on the platform.",
    domain: "future",
  },
  {
    id: "active_learning",
    label: "Smart labeling helper",
    summary: "Picks the most uncertain examples for humans to label next.",
    whyItMatters: "You spend labeling time where it improves models the most.",
    dataExplainer: "Needs live prediction uncertainty from the inference path.",
    domain: "future",
  },
  {
    id: "meta_learning",
    label: "Fast adaptor",
    summary: "Helps models adapt quickly when your org’s patterns shift.",
    whyItMatters: "Reduces retrain lag when products, seasons, or processes change.",
    dataExplainer: "Platform capability tied to broader federated/meta learning readiness.",
    domain: "future",
  },
  {
    id: "neuro_symbolic",
    label: "Rules + AI reasoner",
    summary: "Combines language models with structured business rules.",
    whyItMatters: "Keeps answers creative where allowed and strict where policy matters.",
    dataExplainer: "Today’s equivalent is LLM + injected structured rules; full model is roadmap.",
    domain: "future",
  },
  {
    id: "agentic_planning",
    label: "Agent planner",
    summary: "Learns better multi-step plans from agent trajectories and outcomes.",
    whyItMatters: "Makes agents less brittle on complex, multi-tool work.",
    dataExplainer: "Needs accumulated agent trajectory and outcome data over time.",
    domain: "future",
  },
  {
    id: "world_model",
    label: "Business world model",
    summary: "Long-horizon model of how actions ripple through your org’s outcomes.",
    whyItMatters: "Supports strategy simulation once enough history and causal tools exist.",
    dataExplainer: "Requires months of outcome history plus causal analysis becoming active.",
    domain: "future",
  },
  {
    id: "domain_specific_llm",
    label: "Department specialist LLM",
    summary: "Fine-tunes language models per department tone and vocabulary.",
    whyItMatters: "Sales, support, and finance stop sounding like a generic chatbot.",
    dataExplainer: "Needs a large set of high-quality examples per department.",
    domain: "future",
  },
  {
    id: "federated_learning",
    label: "Cross-org learning",
    summary: "Learn patterns across orgs without sharing raw private data.",
    whyItMatters: "Could improve rare-event models — disabled until legal/consent gates clear.",
    dataExplainer: "Requires legal review, consent, and many participating orgs. Disabled today.",
    domain: "future",
  },
  {
    id: "diffusion_model",
    label: "Image generation",
    summary: "Creates images via a connected generation provider.",
    whyItMatters: "Useful for creative assets inside workflows — not a business predictor.",
    dataExplainer: "Activates when an image-generation connector/provider is wired.",
    domain: "future",
  },
  {
    id: "self_supervised_embeddings",
    label: "Self-taught embeddings",
    summary: "Learns richer vector representations from unlabeled org text.",
    whyItMatters: "Only needed if current embeddings show a clear quality gap.",
    dataExplainer: "Platform activates if retrieval quality gaps justify the cost.",
    domain: "future",
  },
]

export const BUILT_IN_MODEL_GUIDES: Record<string, BuiltInModelGuide> = Object.fromEntries(
  GUIDES.map((g) => [g.id, g]),
)

export function getBuiltInModelGuide(modelId: string): BuiltInModelGuide {
  return (
    BUILT_IN_MODEL_GUIDES[modelId] ?? {
      id: modelId,
      label: modelId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      summary: "Gravitre built-in model for org learning.",
      whyItMatters: "Training on your org’s verified signals makes predictions match your business.",
      dataExplainer: "The progress bar shows how close you are to the minimum data needed for reliable training.",
      domain: "learning" as BuiltInModelDomainId,
    }
  )
}

export function statusTone(status: string): "ready" | "learning" | "planned" | "off" {
  const s = status.toLowerCase()
  if (s === "trained") return "ready"
  if (s === "heuristic") return "learning"
  if (s === "disabled") return "off"
  return "planned"
}

export function statusLabel(status: string): string {
  const s = status.toLowerCase()
  if (s === "trained") return "Trained for your org"
  if (s === "heuristic") return "Learning (rules + partial ML)"
  if (s === "disabled") return "Unavailable"
  if (s === "planned") return "Coming later"
  return status.replace(/_/g, " ")
}

/** Compact chip copy for dense directory cards / table rows. */
export function statusShortLabel(status: string): string {
  const s = status.toLowerCase()
  if (s === "trained") return "Trained"
  if (s === "heuristic") return "Learning"
  if (s === "disabled") return "Off"
  if (s === "planned") return "Roadmap"
  return status.replace(/_/g, " ")
}

export function domainLabel(domainId: BuiltInModelDomainId): string {
  return BUILT_IN_MODEL_DOMAINS.find((d) => d.id === domainId)?.title ?? domainId
}

export type BuiltInModelListItem = {
  id: string
  status: string
  useCases: string[]
  sufficiency: { value: number | null; label: string; available: number; required: number }
  outcomeScore: number | null
  lastTrained: string
  guide: BuiltInModelGuide
}

export function groupBuiltInModels(items: BuiltInModelListItem[]): Array<{
  domain: BuiltInModelDomain
  items: BuiltInModelListItem[]
}> {
  const byDomain = new Map<BuiltInModelDomainId, BuiltInModelListItem[]>()
  for (const item of items) {
    const domainId = item.guide.domain
    const list = byDomain.get(domainId) ?? []
    list.push(item)
    byDomain.set(domainId, list)
  }
  return BUILT_IN_MODEL_DOMAINS.map((domain) => ({
    domain,
    items: (byDomain.get(domain.id) ?? []).sort((a, b) => a.guide.label.localeCompare(b.guide.label)),
  })).filter((g) => g.items.length > 0)
}

export function summarizeBrainHealth(items: BuiltInModelListItem[]): {
  trained: number
  learning: number
  collecting: number
  planned: number
  readyPct: number
} {
  let trained = 0
  let learning = 0
  let collecting = 0
  let planned = 0
  for (const item of items) {
    const tone = statusTone(item.status)
    if (tone === "ready") {
      trained += 1
      if (item.sufficiency.value != null && item.sufficiency.value < 100) collecting += 1
    } else if (tone === "learning") {
      learning += 1
      if (item.sufficiency.value != null && item.sufficiency.value < 100) collecting += 1
    } else {
      planned += 1
    }
  }
  const activatable = trained + learning
  const readyPct = activatable === 0 ? 0 : Math.round((trained / activatable) * 100)
  return { trained, learning, collecting, planned, readyPct }
}
