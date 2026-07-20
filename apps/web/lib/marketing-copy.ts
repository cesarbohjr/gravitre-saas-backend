/**
 * Marketing site copy — smart, technical, helpful, confident.
 * Facts first. Evidence shown. Action-oriented.
 */
export const MARKETING_COPY = {
  hero: {
    badge: "GIBE + operations platform",
    headline: ["Operators with", "org memory"],
    subhead:
      "Gravitre connects your stack, runs workflows, and learns through GIBE — the Gravitre Intelligent Business Engine — with confidence scores, not guesswork.",
    ctaPrimary: "Get Started Free",
    ctaSecondary: "See How It Works",
  },
  stats: [
    { value: "4-layer", label: "Intelligence stack" },
    { value: "Always", label: "Human approval gates" },
    { value: "50", suffix: "+", label: "Connector integrations" },
    { value: "Live", label: "Configured → Executable checks" },
  ],
  intelligenceEngine: {
    badge: "Gravitre Intelligent Business Engine (GIBE)",
    title: "An MCP server with a brain",
    subtitle:
      "Connectors give Gravitre hands. GIBE gives it memory, ML models, and judgment — scoped to your org, verified before it acts.",
    tagline: "Observe → Learn → Recommend → Execute (with approval)",
    layers: [
      {
        title: "Perception",
        description:
          "Connectors, RAG, and event hooks ingest what your business actually does — not generic internet noise.",
      },
      {
        title: "Memory",
        description:
          "Vector search, promoted org memories, entity graph links, and glossary terms — ranked and auditable.",
      },
      {
        title: "Reasoning",
        description:
          "ML catalog models, retrieval rankers, predictive ops packs, and routing that shows why it picked an answer.",
      },
      {
        title: "Autonomy",
        description:
          "Workflow execution, approval gates, failure predictions, and continuous learning from measured outcomes.",
      },
    ],
    capabilities: [
      {
        title: "Connector truth, not theater",
        description:
          "Every integration shows Configured, Authenticated, Healthy, and Executable — so chat and workflows fail before they run, not after.",
      },
      {
        title: "Learning from verified signals",
        description:
          "Query clusters, knowledge gaps, retrieval rankers, and memory promotion train only when your org has enough data — with honest TRAINED / data-gate status.",
      },
      {
        title: "Predict before failure",
        description:
          "Workflow failure alerts from auth expiry, rate limits, missing scopes, and run history — advisory, with recovery steps.",
      },
      {
        title: "Insights you can audit",
        description:
          "Confidence scores, routing traces, ROI reports, and agent profiles — high-level evidence without hidden chain-of-thought.",
      },
      {
        title: "Built-in ML catalog",
        description:
          "Intent classifiers, anomaly detectors, duration forecasters, and domain predictive ops — each with TRAINED / data-gate status inside GIBE.",
      },
      {
        title: "MCP-native execution",
        description:
          "Gravitre AI routes execute, chat, and search modes to the right engine — tools, workflows, and connectors with live availability checks.",
      },
    ],
    example: {
      label: "Example",
      text: "HubSpot is connected, but contact search permission is missing. Confidence: Medium. Complete OAuth scopes before this workflow runs.",
    },
  },
  homeFeatures: [
    {
      title: "Gravitre AI",
      description:
        "Execute tracked work, chat with context, or search records — routed to the right engine with live connector checks.",
    },
    {
      title: "Agents that execute",
      description:
        "Department agents with profiles, health scores, and outcomes — not just chat personas.",
    },
    {
      title: "Workflows with signals",
      description:
        "Build automations, simulate runs, predict failures, and approve before anything hits production.",
    },
    {
      title: "Governed by default",
      description:
        "Approval gates, audit trails, and role permissions — autonomy where you want it, stops where you don't.",
    },
    {
      title: "Live run visibility",
      description:
        "Watch runs succeed, fail, or pause for approval — with duration, steps, and connector context.",
    },
    {
      title: "Insights & Learning",
      description:
        "GIBE surfaces query patterns, memory promotion, predictive ops, and ROI — with honest dashes when measurement is not ready.",
    },
  ],
  howItWorks: {
    eyebrow: "How it works",
    title: "From connected stack to verified action",
    subtitle:
      "Connect tools, assign work to agents, route through GIBE, and approve execution — with evidence at every step.",
    steps: [
      {
        number: "01",
        title: "Connect and verify",
        description:
          "Link HubSpot, Salesforce, Slack, and 50+ systems. Gravitre checks auth, health, and executability before agents touch them.",
      },
      {
        number: "02",
        title: "Observe and learn",
        description:
          "Queries, workflow runs, and retrieval quality feed GIBE — clusters, gaps, rankers, and memory promotion when data gates pass.",
      },
      {
        number: "03",
        title: "Execute with approval",
        description:
          "Agents and workflows act through connectors. High-impact steps wait for human sign-off. Every run leaves an audit trail.",
      },
    ],
  },
  featuresHero: {
    badge: "Platform capabilities",
    headline: ["Everything to run", "AI operations"],
    subtitle:
      "Agents, workflows, connectors, learning, and models — one stack with governance built in.",
    pills: ["GIBE", "Gravitre AI", "Agents", "Workflows", "Learning", "Models"],
  },
  meson: {
    title: "Meson builds systems, not slide decks",
    description:
      "Describe the outcome once. Meson generates agents, training data, and workflows — configured for review before production.",
    bullets: [
      "One prompt → agents, datasets, and workflow drafts",
      "Intent detection from your org context",
      "Executes through connected tools, not mockups",
      "Ships to review — you approve before go-live",
    ],
  },
  heroPills: [
    { label: "Approval before writes" },
    { label: "Verified run outcomes" },
    { label: "Org-scoped learning" },
  ],
  gibeDataFlow: {
    badge: "How GIBE uses your data",
    title: "From your stack to audited action",
    subtitle:
      "Connectors, runs, and queries feed the Gravitre Intelligent Business Engine — scoped to your org, never pooled across customers.",
    steps: [
      {
        title: "Ingest",
        description:
          "Connected tools, RAG sources, workflow runs, and chat queries enter GIBE as org-scoped signals — not generic internet noise.",
      },
      {
        title: "Learn",
        description:
          "Perception normalizes events. Memory stores promoted facts and entities. Reasoning trains rankers and ML models only when data gates pass.",
      },
      {
        title: "Recommend",
        description:
          "Insights, failure predictions, and proactive suggestions surface with confidence scores, routing traces, and plain-language reasons.",
      },
      {
        title: "Execute",
        description:
          "Writes route through approval policy. You get verified links, honest summaries, or a clear failure — every step logged.",
      },
    ],
  },
  transparencyMetrics: {
    badge: "Honest reporting",
    title: "Three tiers. No mixed signals.",
    subtitle:
      "Show what happened, label estimates, and leave gaps open until measured — the same discipline as our transparency blog.",
    tiers: [
      {
        title: "What actually happened",
        description: "Live workflow runs, connector actions, agent tasks, and operational counts from your org.",
        examples: ["Run volume and duration", "Steps completed vs failed", "Approval queue status"],
      },
      {
        title: "What is estimated",
        description:
          "Marketplace time-savings figures and builder projections — labeled at source, never folded into your operational data.",
        examples: ["Hours saved on a template", "Catalog ROI notes from pack authors"],
      },
      {
        title: "What we have not verified yet",
        description:
          "Real-dollar ROI rollups when measurement is not ready — we say so instead of inventing an outcome.",
        examples: ["Cross-department savings totals", "Before/after hour comparisons"],
      },
    ],
    blogLink: {
      label: "Read how we measure",
      href: "/blog/measuring-what-ai-changes",
    },
  },
  marketplace: {
    badge: "Gravitre Marketplace",
    title: "60+ installable assets — not blank canvases",
    subtitle:
      "Workflow templates, department packs, agents, and knowledge — connector checks before install, human approval on writes.",
    stats: [
      { value: "60+", label: "Catalog assets" },
      { value: "19", label: "Workflow templates" },
      { value: "6", label: "Department packs" },
    ],
    packs: [
      { name: "RevOps", description: "Pipeline hygiene, deal routing, and CRM sync workflows" },
      { name: "Support", description: "Ticket triage, escalation, and CSAT follow-up" },
      { name: "Marketing", description: "Campaign workflows, lead routing, and content ops" },
      { name: "Finance", description: "Invoice processing, expense review, and close tasks" },
      { name: "HR", description: "Onboarding checklists and employee request routing" },
      { name: "Operations", description: "Cross-team handoffs and incident response playbooks" },
    ],
    bullets: [
      "Readiness check before install — missing connectors show upfront",
      "Same approval gates as chat and custom workflows",
      "Org-owned publishes support version history and rollback",
    ],
    cta: { label: "Browse Marketplace", href: "/marketplace" },
    blogLink: { label: "See the template library", href: "/blog/workflow-templates-library" },
  },
  useCases: {
    badge: "Use cases",
    title: "Where teams start",
    subtitle: "Patterns from the product and catalog — not hypothetical case studies with invented ROI.",
    cases: [
      {
        department: "Support",
        title: "First-pass ticket triage",
        description:
          "Route and categorize inbound tickets, hand off to humans with context. See live run counts — not projected savings dressed as data.",
        surfaces: ["Workflows", "Agents", "Approvals"],
      },
      {
        department: "Sales",
        title: "CRM enrichment and follow-up",
        description:
          "Pull connected tool data into agents and workflows. Verified links to records created or updated when a write succeeds.",
        surfaces: ["Gravitre AI", "Connectors", "Intelligence"],
      },
      {
        department: "IT and Security",
        title: "Threat intel monitoring",
        description:
          "Steady feed from connected sources with routing traces, confidence scores, and audit history.",
        surfaces: ["Agents", "Audit", "Sources"],
      },
      {
        department: "Leadership",
        title: "Operational visibility",
        description:
          "Activity metrics, Insights confidence scores, and honest dashes where dollar ROI is not measured yet.",
        surfaces: ["Metrics", "Insights", "Reports"],
      },
    ],
  },
  governanceStack: {
    badge: "Governance and AI stack",
    title: "How Gravitre thinks before it acts",
    subtitle:
      "Human approval, org-scoped models, and security controls built into execution — not bolted on after the fact.",
    governance: [
      {
        title: "Human-in-the-loop approval",
        description:
          "Every write waits on your policy. Chat, guided tasks, Marketplace installs, and workflows use the same gate.",
      },
      {
        title: "Audit trail",
        description:
          "Approvals, connector writes, and run outcomes — reviewable and exportable from your audit page.",
      },
      {
        title: "Role-based access",
        description:
          "Who can approve, run agents, or publish to Marketplace — controlled from Settings and org roles.",
      },
    ],
    aiStack: [
      {
        title: "Org-scoped LLM routing",
        description:
          "Gravitre AI routes execute, chat, and search with live connector checks — MCP-native, not pooled customer training.",
      },
      {
        title: "Built-in ML catalog",
        description:
          "Intent classifiers, anomaly detectors, rankers, and predictive ops — each with TRAINED / data-gate status per org.",
      },
      {
        title: "Memory and retrieval",
        description:
          "Vector search, promoted memories, entity graph, and glossary — ranked with confidence, not hidden chain-of-thought.",
      },
    ],
    links: [
      { label: "AI transparency and approval", href: "/blog/ai-transparency-and-approval" },
      { label: "Security", href: "/security" },
    ],
  },
  integrationStrip: {
    label: "Connector catalog includes",
    note: "Live Configured → Executable checks on every integration you connect.",
  },
  differentiators: [
    {
      title: "Evidence over hype",
      description: "Confidence scores, data gates, and explicit insufficient-data states — never fake green checks.",
    },
    {
      title: "Executable connectors",
      description: "Live OAuth introspection and scope checks — the same truth in chat, workflows, and the connectors page.",
    },
    {
      title: "Org-scoped learning",
      description: "Models and memories train on your queries and runs — not pooled across customers.",
    },
    {
      title: "Advisory predictions",
      description: "Failure alerts, SLA risk, and optimization suggestions stay recommendations until you act.",
    },
  ],
  cta: {
    title: "Ready to run AI like an operator?",
    subtitle: "Connect your stack. Watch Gravitre learn. Approve what executes.",
  },
  about: {
    principles: [
      {
        title: "Facts before forecasts",
        description: "Show the number, the source, and the confidence — then recommend the next step.",
      },
      {
        title: "Amplify operators",
        description: "Agents handle repetition. Humans keep judgment, approvals, and accountability.",
      },
      {
        title: "Transparent by design",
        description: "Routing traces and readiness badges — no black-box chain-of-thought, no theater.",
      },
    ],
  },
  meta: {
    title: "Gravitre — AI operations with GIBE",
    description:
      "Connect your stack, run agents and workflows, and learn from verified outcomes. GIBE (Gravitre Intelligent Business Engine): memory, ML catalog, predictive ops, and MCP-native execution with approval gates.",
    keywords: [
      "AI operations platform",
      "GIBE",
      "Gravitre Intelligent Business Engine",
      "AI agents",
      "workflow automation",
      "MCP server",
      "org learning",
      "predictive operations",
      "connector health",
    ],
  },
  pricing: {
    badge: "Plans for operators",
    headline: ["Intelligence included.", "Scale when ready."],
    subhead:
      "Every plan includes Gravitre AI, connector health checks, and governed execution. Higher tiers add Meson, cross-team agents, and GIBE admin surfaces.",
    subheadNote: "Pay for outputs and team seats — not buzzword tiers.",
    comparisonIntro:
      "See what each plan includes. GIBE features (Insights, Learning, failure predictions, built-in ML) are available on all paid plans; depth scales with usage.",
    intelligenceRows: [
      { feature: "Insights & confidence scores", node: true, control: true, command: true },
      { feature: "Connector executability checks", node: true, control: true, command: true },
      { feature: "Learning admin (GIBE)", node: false, control: true, command: true },
      { feature: "Predictive ops & failure alerts", node: false, control: true, command: true },
      { feature: "Custom training & model registry", node: false, control: false, command: true },
    ],
    faqLearning:
      "Yes — on Control and Command. GIBE observes queries, workflow runs, and retrieval quality, then surfaces clusters, gaps, built-in ML readiness, and memory promotion when data gates pass. Nothing auto-applies without review.",
    faqMeson:
      "Meson builds agents, datasets, and workflow drafts from one prompt — configured for your review before production. Available on Control and Command.",
    cta: {
      title: "Start with verified execution.",
      subtitle: "7-day trial. Connect a connector. See what's executable before anything runs.",
    },
  },
  changelog: {
    subtitle:
      "Shipped features, measured improvements, and honest fixes — including the GIBE rollout.",
    releases: [
      {
        version: "3.0.0",
        date: "July 5, 2026",
        title: "Gravitre Intelligent Business Engine (GIBE)",
        description:
          "Org-scoped learning, connector executability, predictive ops, built-in ML catalog, and Insights surfaces — one engine behind chat, workflows, and admin.",
        type: "major",
        highlights: [
          "GIBE: query clusters, memory promotion, retrieval rankers, and predictive ops with data-gate honesty",
          "Canonical connector availability (Configured → Executable) across chat and UI",
          "Insights, Learning, Training, and Models surfaces with unified copy and routes",
          "Built-in ML catalog with TRAINED / not_trained / data_gate status per org",
          "Workflow failure predictions from auth, scopes, and run history",
        ],
      },
      {
        version: "2.5.0",
        date: "June 22, 2026",
        title: "MCP-native Gravitre AI",
        description:
          "Execute, chat, and search modes with live connector checks — an MCP server with org memory and routing traces.",
        type: "feature",
        highlights: [
          "Gravitre AI workspace with mode routing and conversation persistence",
          "Agent profiles with health, performance, and outcome tabs",
          "Routing traces and confidence badges — evidence without chain-of-thought",
          "Hybrid memory fusion and entity graph relationships",
        ],
      },
    ],
  },
  docs: {
    title: "Documentation",
    description:
      "Guides for GIBE, Gravitre AI, connectors, workflows, and API — facts-first setup for operators and builders.",
    quickLinks: [
      {
        iconKey: "Zap",
        title: "Quickstart",
        description: "Connect a tool, verify executability, run your first workflow",
        href: "/docs/getting-started/quickstart",
      },
      {
        iconKey: "Brain",
        title: "GIBE (Learning)",
        description: "Built-in ML, memory promotion, query clusters, and quality evaluation",
        href: "/docs/guides/how-to/org-learning",
      },
      {
        iconKey: "Bot",
        title: "Gravitre AI",
        description: "Execute, chat, and search — with connector availability checks",
        href: "/docs/guides/how-to/ai-operator",
      },
      {
        iconKey: "Database",
        title: "Connectors",
        description: "OAuth, live health, Configured → Executable readiness",
        href: "/docs/guides/how-to/connectors",
      },
      {
        iconKey: "Workflow",
        title: "Workflows",
        description: "Build, simulate, schedule, and predict failures",
        href: "/docs/guides/how-to/workflows",
      },
      {
        iconKey: "Activity",
        title: "Failure alerts",
        description: "Pre-run warnings from auth expiry and run history",
        href: "/docs/guides/how-to/failure-alerts",
      },
      {
        iconKey: "BarChart3",
        title: "Metrics",
        description: "Run volume, latency, and detected anomalies",
        href: "/docs/guides/how-to/metrics",
      },
      {
        iconKey: "Code",
        title: "API quickstart",
        description: "REST + GIBE/intelligence endpoints with approval gates",
        href: "/docs/api/quickstart",
      },
    ],
    integrationsIntro:
      "Connect your stack with live health checks. Gravitre verifies auth, scopes, and executability before agents or workflows act.",
    faqIntro:
      "Common questions about GIBE, billing, connectors, and execution — search or browse by category.",
  },
} as const
