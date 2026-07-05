import type { BlogPost } from "../types"
import { SITE_URL } from "../types"

export const workflowTemplatesPost: BlogPost = {
  slug: "workflow-templates-library",
  title: "Introducing 50+ Pre-Built Workflow Templates",
  description:
    "Ship automation faster with curated workflow templates for sales, marketing, finance, and ops — install from the Marketplace with connector readiness checks.",
  excerpt:
    "Starting from a blank canvas slows teams down. Our template library gives you governed starting points you can adapt, simulate, and approve before production.",
  category: "Product",
  author: {
    name: "Priya Patel",
    role: "VP Design, Gravitre",
    sameAs: [`${SITE_URL}/about`],
  },
  datePublished: "2026-03-21",
  dateModified: "2026-03-21",
  displayDate: "March 21, 2026",
  readTime: "5 min read",
  heroImage: "",
  heroGradient: "from-amber-50 via-white to-emerald-50",
  heroAlt: "Grid of workflow cards representing pre-built automation templates.",
  keywords: [
    "workflow templates",
    "automation marketplace",
    "RevOps workflows",
    "AI operations",
    "workflow automation library",
  ],
  takeaways: [
    "Templates encode proven patterns — triggers, connector steps, and approval points — so teams start from 80%, not zero.",
    "Each template lists required connectors; install checks verify you are executable before go-live.",
    "Dry-run and simulation help you see failure predictions and duration estimates before scheduling.",
    "Categories span sales, marketing, finance, support, and cross-functional ops — not generic RPA demos.",
    "Templates are starting points: publish versions, add Expert Review nodes, and wire to your environments.",
  ],
  faqs: [
    {
      question: "Are templates production-ready out of the box?",
      answer:
        "They are production-shaped, not production-magic. You still connect OAuth integrations, choose an environment, and approve publishes. Templates save design time — they do not bypass governance.",
    },
    {
      question: "What if I am missing a connector?",
      answer:
        "The Marketplace install flow surfaces missing prerequisites. Connect HubSpot, Salesforce, Slack, or other vendors first, then re-run the install check.",
    },
    {
      question: "Can we customize templates for our org?",
      answer:
        "Yes. Install into your org, edit in the workflow builder, publish a version, and optionally save derivatives as org-only Marketplace assets.",
    },
  ],
  Content: () => (
    <>
      <p>
        Most teams do not need another empty workflow canvas. They need a governed starting point: the right trigger, the
        right connector sequence, and the right approval step for their stack.
      </p>
      <p>
        Today we are shipping <strong>50+ pre-built workflow templates</strong> in the Gravitre Marketplace — curated
        for sales, marketing, finance, support, and operations use cases that show up in every RevOps standup.
      </p>

      <h2>What is in the library</h2>
      <p>
        Templates include scheduled and manual triggers, connector actions (HubSpot, Salesforce, Slack, Google
        Workspace, and more), branching, and — where writes are risky —{" "}
        <strong>approval or Expert Review</strong> nodes. Examples:
      </p>
      <ul className="mt-4 list-disc space-y-2 pl-6 text-base">
        <li>Sync new CRM records and notify owners in Slack on failure</li>
        <li>Weekly pipeline summaries with links back to source deals</li>
        <li>Route high-value opportunities through human sign-off before stage changes</li>
        <li>Incident follow-ups from PagerDuty into ticketing systems</li>
      </ul>
      <p>
        Each listing shows required connectors and plan compatibility so you know upfront what to connect.
      </p>

      <h2>Install with executability checks</h2>
      <p>
        One-click install is only useful if the workflow can actually run in your org. We run the same{" "}
        <strong>Configured → Executable</strong> checks you see on the Connectors page before marking a template{" "}
        <strong>Ready to install</strong>. Missing OAuth scopes surface as fixable blockers, not mysterious run failures
        three days later.
      </p>

      <h2>Simulate before you schedule</h2>
      <p>
        After install, use <strong>dry-run</strong> and GIBE-backed <strong>failure predictions</strong> where your org
        has enough run history. Simulation and pre-run panels show estimated duration and advisory warnings — auth
        expiry, rate limits, missing scopes — so you approve production schedules with evidence.
      </p>

      <h2>Built for adaptation, not lock-in</h2>
      <p>
        Templates are forks, not cages. Duplicate steps, add Meson-generated agents, wire custom Training instructions,
        or publish an org-specific variant to your private Marketplace catalog. The goal is speed with guardrails — the
        same philosophy behind <a href="/features">Gravitre workflows</a>.
      </p>
      <p>
        Browse the catalog from <a href="/docs/guides/how-to/marketplace">Marketplace docs</a> or open{" "}
        <strong>BUILD → Marketplace</strong> after sign-up and filter by Workflow templates.
      </p>
    </>
  ),
}
