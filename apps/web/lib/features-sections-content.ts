import type { LucideIcon } from "lucide-react"
import {
  Activity,
  AlertTriangle,
  Boxes,
  Brain,
  CheckCircle2,
  Database,
  FileCheck,
  FlaskConical,
  Gauge,
  GitBranch,
  KeyRound,
  Layers,
  LineChart,
  ListChecks,
  Lock,
  MessageSquare,
  Network,
  Package,
  PlugZap,
  Radar,
  ScrollText,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  Wand2,
  Workflow,
  Zap,
} from "lucide-react"
import type { FeaturesSectionId } from "@/lib/features-nav"

export type FlowStep = { label: string; sub: string }
export type Capability = { icon: LucideIcon; title: string; desc: string }
export type Spec = { value: string; label: string }

export type SectionContent = {
  /** Short punchy sentence shown under the primary showcase. */
  takeaway: string
  flowTitle: string
  flowNote?: string
  flow: FlowStep[]
  capabilitiesTitle: string
  capabilities: Capability[]
  specs: Spec[]
}

export const SECTION_CONTENT: Partial<Record<FeaturesSectionId, SectionContent>> = {
  "gravitre-ai": {
    takeaway: "One place to ask, execute, and search — with a live check before anything writes.",
    flowTitle: "From prompt to result",
    flowNote: "Every write pauses for approval before it runs.",
    flow: [
      { label: "Ask", sub: "Natural language" },
      { label: "Route", sub: "Right agent + tools" },
      { label: "Approve", sub: "Confirm any write" },
      { label: "Report", sub: "Traceable result" },
    ],
    capabilitiesTitle: "What you can do",
    capabilities: [
      { icon: MessageSquare, title: "Chat", desc: "Ask questions and get context-aware answers grounded in your data." },
      { icon: Zap, title: "Execute", desc: "Trigger real actions across connected tools, gated by approval." },
      { icon: Search, title: "Search", desc: "Find records, docs, and history across every connector at once." },
      { icon: PlugZap, title: "Live checks", desc: "Connector readiness is verified before a task can run." },
    ],
    specs: [
      { value: "50+", label: "Connectors reachable" },
      { value: "0", label: "Silent writes" },
      { value: "Live", label: "Readiness checks" },
    ],
  },
  agents: {
    takeaway: "Specialized department agents you can inspect, trust, and hold to verified outcomes.",
    flowTitle: "How an agent runs",
    flowNote: "Permissions and approvals apply at every step.",
    flow: [
      { label: "Assign role", sub: "Sales, RevOps, support…" },
      { label: "Connect tools", sub: "Scoped permissions" },
      { label: "Run tasks", sub: "Async with progress" },
      { label: "Verify", sub: "Outcome + evidence" },
    ],
    capabilitiesTitle: "Built for real teams",
    capabilities: [
      { icon: Users, title: "Department profiles", desc: "Agents shaped for a function, not a generic bot." },
      { icon: Activity, title: "Health signals", desc: "See status, load, and recent activity at a glance." },
      { icon: CheckCircle2, title: "Verified outcomes", desc: "Results carry evidence you can audit, not just claims." },
      { icon: KeyRound, title: "Role-based access", desc: "Each agent only touches the tools you grant it." },
    ],
    specs: [
      { value: "Per-role", label: "Permissions" },
      { value: "24/7", label: "Async execution" },
      { value: "Audited", label: "Every outcome" },
    ],
  },
  workflows: {
    takeaway: "Design, simulate, and pressure-test automations before a single real action fires.",
    flowTitle: "Build with confidence",
    flowNote: "Simulate and predict failures before going live.",
    flow: [
      { label: "Design", sub: "Visual builder" },
      { label: "Simulate", sub: "Dry-run the path" },
      { label: "Predict", sub: "Flag likely failures" },
      { label: "Approve", sub: "Then run for real" },
    ],
    capabilitiesTitle: "Automation you can trust",
    capabilities: [
      { icon: Workflow, title: "Visual builder", desc: "Compose multi-step flows without writing glue code." },
      { icon: FlaskConical, title: "Simulation", desc: "Dry-run a workflow to see what it would do first." },
      { icon: AlertTriangle, title: "Failure prediction", desc: "Surface risky steps before they touch production." },
      { icon: ShieldCheck, title: "Approval gates", desc: "Insert human sign-off anywhere a write happens." },
    ],
    specs: [
      { value: "Dry-run", label: "Before live" },
      { value: "Step-level", label: "Approvals" },
      { value: "Predicted", label: "Failure points" },
    ],
  },
  meson: {
    takeaway: "Describe the outcome once — Meson drafts the agents, data, and workflow for your review.",
    flowTitle: "One prompt to a draft",
    flowNote: "Nothing goes live until you review and approve it.",
    flow: [
      { label: "Describe", sub: "Plain-language goal" },
      { label: "Draft", sub: "Agents + data + flow" },
      { label: "Review", sub: "Edit every piece" },
      { label: "Ship", sub: "Approve to activate" },
    ],
    capabilitiesTitle: "From idea to build",
    capabilities: [
      { icon: Wand2, title: "Prompt to build", desc: "Turn a sentence into a working starting point." },
      { icon: Boxes, title: "Agents + datasets", desc: "Get the supporting pieces drafted together, not separately." },
      { icon: GitBranch, title: "Workflow drafts", desc: "Receive an editable flow, not a black box." },
      { icon: FileCheck, title: "Review-first", desc: "Every generated asset waits for your approval." },
    ],
    specs: [
      { value: "1 prompt", label: "To a draft" },
      { value: "Editable", label: "Every asset" },
      { value: "Review", label: "Before activation" },
    ],
  },
  integrations: {
    takeaway: "50+ connectors with an honest readiness state — you always know what can actually run.",
    flowTitle: "Connected to executable",
    flowNote: "A connector must pass readiness before agents can use it.",
    flow: [
      { label: "Connect", sub: "OAuth or keys" },
      { label: "Configure", sub: "Scopes + mapping" },
      { label: "Check", sub: "Live readiness test" },
      { label: "Executable", sub: "Ready for agents" },
    ],
    capabilitiesTitle: "Connectors, done right",
    capabilities: [
      { icon: Database, title: "50+ connectors", desc: "CRMs, warehouses, support, marketing, and more." },
      { icon: Gauge, title: "Readiness state", desc: "Every connector shows Configured → Executable clearly." },
      { icon: PlugZap, title: "Bring your own", desc: "Add custom connectors alongside the built-in catalog." },
      { icon: Radar, title: "Live verification", desc: "Health is checked before a task depends on it." },
    ],
    specs: [
      { value: "50+", label: "Connectors" },
      { value: "2-state", label: "Readiness model" },
      { value: "BYO", label: "Custom connectors" },
    ],
  },
  governance: {
    takeaway: "Approval gates, audit trails, and RBAC baked in — plus full transparency on the AI stack.",
    flowTitle: "Control at every write",
    flowNote: "Nothing writes without a gate and a record.",
    flow: [
      { label: "Request", sub: "Agent proposes" },
      { label: "Approve", sub: "Human sign-off" },
      { label: "Act", sub: "Scoped execution" },
      { label: "Audit", sub: "Immutable trail" },
    ],
    capabilitiesTitle: "Trust by design",
    capabilities: [
      { icon: ShieldCheck, title: "Approval gates", desc: "Require sign-off before any action that changes data." },
      { icon: ScrollText, title: "Audit trails", desc: "Every decision and action is logged and reviewable." },
      { icon: Lock, title: "RBAC", desc: "Granular roles control who and what can do what." },
      { icon: Layers, title: "Stack transparency", desc: "See the models and providers behind every answer." },
    ],
    specs: [
      { value: "100%", label: "Writes gated" },
      { value: "Immutable", label: "Audit log" },
      { value: "Role-based", label: "Access control" },
    ],
  },
  marketplace: {
    takeaway: "60+ installable templates, packs, and agents to skip the blank canvas.",
    flowTitle: "Install and run",
    flow: [
      { label: "Browse", sub: "60+ listings" },
      { label: "Install", sub: "One click" },
      { label: "Configure", sub: "Connect your tools" },
      { label: "Run", sub: "Approve and go" },
    ],
    capabilitiesTitle: "Start from proven work",
    capabilities: [
      { icon: Package, title: "Templates", desc: "Prebuilt starting points for common operations." },
      { icon: Boxes, title: "Packs", desc: "Bundled agents and workflows for a whole function." },
      { icon: Users, title: "Agents", desc: "Ready-made department agents you can tailor." },
      { icon: Zap, title: "One-click install", desc: "Add to your workspace and configure in minutes." },
    ],
    specs: [
      { value: "60+", label: "Listings" },
      { value: "1-click", label: "Install" },
      { value: "Editable", label: "After install" },
    ],
  },
  intelligence: {
    takeaway: "Connectors give Gravitre hands. GIBE gives it memory, models, and judgment — scoped to your org.",
    flowTitle: "The learning loop",
    flowNote: "Recommendations only execute with approval.",
    flow: [
      { label: "Observe", sub: "Org-scoped signals" },
      { label: "Learn", sub: "Memory + ML catalog" },
      { label: "Recommend", sub: "Auditable routing" },
      { label: "Execute", sub: "With approval" },
    ],
    capabilitiesTitle: "Inside GIBE",
    capabilities: [
      { icon: Brain, title: "Memory", desc: "Retains what your business actually does, not internet noise." },
      { icon: Layers, title: "ML catalog", desc: "Models and glossary terms, ranked and auditable." },
      { icon: Network, title: "Routing traces", desc: "See why GIBE picked a given answer or agent." },
      { icon: Lock, title: "Org-scoped", desc: "Learning stays within your organization boundary." },
    ],
    specs: [
      { value: "Org-scoped", label: "Learning" },
      { value: "Auditable", label: "Routing" },
      { value: "4-layer", label: "Intelligence stack" },
    ],
  },
  insights: {
    takeaway: "Honest, three-tier reporting — live counts, labeled estimates, and open gaps we don't fake.",
    flowTitle: "How we report",
    flowNote: "Same three-tier honesty as our engineering blog.",
    flow: [
      { label: "Measure", sub: "Live activity" },
      { label: "Label", sub: "Fact vs estimate" },
      { label: "Disclose", sub: "Name the gaps" },
    ],
    capabilitiesTitle: "Where teams start",
    capabilities: [
      { icon: LineChart, title: "Live metrics", desc: "Real activity counts, not invented ROI." },
      { icon: ListChecks, title: "Labeled estimates", desc: "Projections are clearly marked as estimates." },
      { icon: AlertTriangle, title: "Open gaps", desc: "We name what isn't measured yet instead of hiding it." },
      { icon: Sparkles, title: "Clear use cases", desc: "Concrete starting points for each department." },
    ],
    specs: [
      { value: "3-tier", label: "Reporting model" },
      { value: "Labeled", label: "Every estimate" },
      { value: "Honest", label: "About gaps" },
    ],
  },
}

export function getSectionContent(id: FeaturesSectionId): SectionContent | undefined {
  return SECTION_CONTENT[id]
}
