/**
 * Canonical labels and copy for Insights, Learning, Training, and Models surfaces.
 * Tone: smart, concise, practical, transparent — facts first, action-oriented.
 */
import { APP_ROUTES } from "@/lib/app-routes"

export const SURFACE_COPY = {
  insights: {
    title: "Insights",
    shortTitle: "Insights",
    description:
      "What Gravitre observed, how confident it is, and why it recommended each action.",
    emptyTitle: "Collecting signals",
    emptyDescription:
      "Outcome events and confidence scores appear here as agents finish work with measurable results.",
    route: APP_ROUTES.intelligence,
  },
  learning: {
    title: "Learning",
    shortTitle: "Learning",
    description:
      "How Gravitre learns from queries, memory, and search quality — verified signals only.",
    route: APP_ROUTES.learning,
    step: "Observe",
    stepSummary: "Watch queries, memory, and search quality improve over time.",
  },
  training: {
    title: "Training",
    shortTitle: "Training",
    description:
      "Shape agent behavior with examples, training jobs, and custom instructions.",
    badge: "Agent behavior",
    heroTitle: "Teach agents with real examples",
    heroDescription:
      "Add datasets, run fine-tunes, and assign models to workflow agents. Starts from what Learning already detected.",
    route: APP_ROUTES.training,
    step: "Train",
    stepSummary: "Examples, jobs, and instructions that change how agents respond.",
  },
  models: {
    title: "Models",
    shortTitle: "Models",
    description:
      "Register, version, and deploy models your workflows and services can call.",
    badge: "Production models",
    heroTitle: "Deploy models to workflows",
    heroDescription:
      "Track versions, wire datasets from Training, and expose inference to automations. For org-wide learning signals, see Learning.",
    route: APP_ROUTES.models,
    step: "Deploy",
    stepSummary: "Versioned models ready for workflows and API calls.",
  },
  builtInModels: {
    title: "Built-in models",
    shortTitle: "Built-in",
    description:
      "Gravitre's org ML brain — plain-language models that learn from your workflows, CRM, support, and chat signals.",
    intro:
      "These are Gravitre’s built-in learners for your organization. Each card explains what the model does, why training matters, and how close you are to its data quality gate.",
    emptyTitle: "No catalog models yet",
    emptyDescription: "Built-in models appear here once ML catalog is enabled for your org.",
    route: APP_ROUTES.builtInModels,
  },
  learningLoop: {
    title: "Learning loop",
    subtitle: "Observe → Train → Deploy",
    description: "Three connected steps: learn from usage, fine-tune agents, deploy production models.",
  },
  hubLinks: {
    agents: {
      title: "Agent intelligence",
      summary: "Health, performance, learning, and outcomes — not the live team roster.",
      route: APP_ROUTES.intelligenceAgents,
    },
    builtIn: {
      title: "Built-in models",
      summary: "Org ML brain — what each model does, why train it, and data readiness.",
      route: APP_ROUTES.builtInModels,
    },
    predictive: {
      title: "Predictive ops",
      summary: "SLA, deal-loss, capacity, and workflow risk by domain.",
      route: APP_ROUTES.intelligencePredictive,
    },
    memory: {
      title: "Memory",
      summary: "Promoted memories and knowledge graph connections.",
      route: APP_ROUTES.intelligenceMemory,
    },
    reports: {
      title: "Reports",
      summary: "ROI metrics and department scorecards.",
      route: APP_ROUTES.intelligenceReports,
    },
  },
  stats: {
    outcomeEvents: "Outcome events (7d)",
    avgConfidence: "Avg confidence",
    recommendationsCreated: "Recommendations created",
    recommendationsRejected: "Recommendations rejected",
    registered: "Registered",
    deployed: "Deployed",
    ready: "Ready",
    inTraining: "In training",
    datasets: "Datasets",
    activeJobs: "Active jobs",
    instructions: "Instructions",
  },
  sections: {
    routingTrace: "How Gravitre routed this",
    routingTraceHint: "High-level stages only — no raw prompts or hidden reasoning.",
    latestSimulation: "Latest simulation",
    latestSimulationHint: "Pre-execution estimates from historical evidence.",
    recommendationSummary:
      "Recommendations combine org signals, retrieval quality, and model routing. Each stays advisory until you approve or reject it.",
  },
  adminTabs: {
    overview: "Overview",
    memory: "Memory",
    relationships: "Relationships",
    evaluation: "Quality",
    outcomes: "Outcomes",
    learning: "Trends",
    engine: "Engine",
    performance: "Performance",
  },
  pages: {
    agents: {
      title: "Agents",
      rosterTitle: "AI Team",
      description: "Agents that run workflows, answer chat, and act on your connectors.",
      profileTitle: "Agent profile",
      profileListHint: "Pick an agent to review measured health, performance, learning, and outcomes.",
      profileEmpty: "Create an agent to see its intelligence profile.",
      operateHint: "Chat, knowledge, and assignments live on the AI Team surface.",
      insightsHint: "Measured health and outcomes live on Agent intelligence.",
    },
    workflows: {
      title: "Workflows",
      description: "Automations across your connectors — status, runs, and failure signals in one place.",
    },
    runs: {
      title: "Runs",
      headline: "Execution timeline",
      description: "Live workflow runs — success, failure, and duration.",
    },
    goals: {
      title: "Goals",
      description: "Business outcomes tied to workflows, with approval gates before anything executes.",
    },
    metrics: {
      title: "Metrics",
      headline: "Platform metrics",
      description: "Run volume, latency, and throughput — detected anomalies highlighted.",
    },
    failureAlerts: {
      title: "Failure alerts",
      description: "Predicted workflow failures from connector auth, rate limits, scopes, and run history.",
    },
    ai: {
      title: "Chat",
      description: "Execute work, chat with context, or search records — routed to the right engine.",
    },
    connectors: {
      title: "Connectors",
      headline: "Connectors",
      description: "Connected systems Gravitre reads from and writes to.",
    },
    memory: {
      title: "Memory",
      description:
        "Promoted memories, auto-promotion audit trail, and knowledge graph — org-scoped only.",
      tabPromoted: "Promoted memories",
      tabAuto: "Auto-promotions",
      tabGraph: "Knowledge graph",
      autoHint: "Recent automatic promotions from the learning engine.",
      autoAdminLink: "Open memory promotion admin",
      graphHint:
        "Entity relationships and which graph nodes have promoted memories in the audit trail.",
    },
    reports: {
      title: "Reports",
      description:
        "ROI metrics and department scorecards — honest dashes when measurement is unavailable.",
      tabRoi: "ROI",
      tabScorecards: "Department scorecards",
      tabExecutive: "Executive scorecard",
      tabCustomerSuccess: "Customer Success",
      tabProspecting: "Prospecting",
      tabMarketing: "Marketing",
      tabRevOps: "RevOps",
      tabAiSearch: "AI Search",
      tabFinance: "Finance",
      tabHrTalent: "HR & Talent",
      tabPlatformHealth: "Platform Health",
    },
    predictive: {
      title: "Predictive ops",
      description:
        "Domain model packs with TRAINED / not_trained / data_gate status. All outputs are advisory only.",
    },
    assignments: {
      title: "Assignments",
      description: "Work routed to agents with clear ownership and status.",
    },
    marketplace: {
      title: "Marketplace",
      description: "Agents, workflows, and connector packs ready to install.",
    },
  },
  insightsHealth: {
    title: "Insights health",
    subtitle: "Org-wide trust, maturity, and domain health — measured from real platform signals.",
    warmingTitle: "Insights are warming up",
    warmingHint: "Run workflows and connect tools to begin learning.",
    reportsLink: "Reports",
  },
  learningAdmin: {
    businessImpactTitle: "Business impact",
    businessImpactHint: "Score from pending recommendations and measured outcomes.",
    revenueRiskTitle: "Revenue risk",
    knowledgeGapsTitle: "Knowledge gaps",
    queryClustersTitle: "Query clusters",
    failedSearchesTitle: "Failed searches",
    banditTitle: "Strategy bandit",
    memoryConflictsTitle: "Memory conflicts",
    evaluationQualityTitle: "Answer quality",
    evaluationQualityHint: "Weighted score from retrieval, grounding, and user feedback.",
    scoredResponsesTitle: "Scored responses",
    learningProgressHint: (logged: number, needed: number, runs: number, runsNeeded: number) =>
      `${logged} of ${needed} queries logged · ${runs} of ${runsNeeded} workflow runs observed`,
  },
} as const
