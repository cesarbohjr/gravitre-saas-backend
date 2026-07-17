import type { BlogPost } from "../types"
import { createBlogDates } from "../blog-dates"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

export const aiTransparencyApprovalPost: BlogPost = {
  slug: "ai-transparency-and-approval",
  title: "AI Transparency and the Approval Question",
  description:
    "What Gravitre actually shows before a write runs: catalog-backed approval gates across chat, ReAct, and canvas, verified outputs, audit links, and honest limits on citations and assumptions.",
  excerpt:
    "Transparency in AI automation is not a values slide. It is whether a write can run without a human, whether you can open the record it created, and whether the product tells you when it inferred something instead of knowing it.",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  ...createBlogDates("2026-07-17"),
  readTime: "9 min read",
  heroImage: "",
  heroGradient: "from-emerald-50 via-white to-slate-100",
  heroAlt:
    "Layered diagram of approval gates, verified outputs, and audit links in an AI automation workflow.",
  keywords: [
    "AI transparency",
    "explainable AI automation",
    "human in the loop approvals",
    "AI audit trail",
    "verified AI output",
    "AI governance",
    "write approval gate",
  ],
  takeaways: [
    "Write actions in chat, ReAct, and canvas workflow runs are checked against the same catalog-derived write authority, not per-template toggles.",
    "Members can request writes; admins (or HITL approvers) must approve before execution. The UI says so explicitly when your request is queued.",
    "Successful chat writes must return a verifiable body or deep link, or the run fails with unverifiable_output instead of a silent success.",
    "Assumption notes surface inferred connector plan values (for example a default list name), distinct from stated facts, on a narrow set of paths today.",
    "Sources checked in chat shows real knowledge citations when search returns hits. When it does not, the product links to Sources rather than inventing citations.",
    "Audit export and the /audit page exist, but the UI reads audit_logs; high-volume events also land in audit_events with dual-write gap logging.",
  ],
  faqs: [
    {
      question: "Does every write require approval?",
      answer:
        "Every catalog-classified write goes through write authority derived from the action schema. Org HITL policy and role (admin/owner vs member) determine whether you confirm locally or the request queues for an approver. Reads do not use the same gate.",
    },
    {
      question: "Do canvas workflows bypass chat governance?",
      answer:
        "No. Canvas execute uses canvas_write_gate with the same catalog write floor as chat and ReAct. Production re-verification (STA-322) showed a canvas write stopping at pending_approval with zero tool.invoke.completed events before approval.",
    },
    {
      question: "Can I see why Gravitre suggested an action?",
      answer:
        "Heuristic recommendations on Intelligence show kind, a plain-language reason, and an evidence object. They are advisory only (no Execute button). That is not the same as a formal reason-code taxonomy, but it is live and inspectable.",
    },
    {
      question: "What happens if a connector returns no deep link?",
      answer:
        "On the chat write path, Gravitre requires a non-empty summary body or result_url. If neither is present, the run fails with error_code unverifiable_output and the panel explains the gap. Many read actions and some verified-write batches allow null result_url by design; we do not claim universal deep links.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>If you cannot answer who approved a write, what was inferred, and where the record lives, you do not have transparency. You have a chatbot with API keys.</strong>
      </p>
      <p>
        This post lists what Gravitre ships today for explainability and approval. Where something is partial or still hardening, we say so. That discipline is the point: a claim does not belong in customer-facing copy unless it maps to a feature, a trace, or a mechanism already in production.
      </p>

      <h2>One write gate, three paths</h2>
      <p>
        High-impact automation arrives through chat, through ReAct tool routing, and through canvas workflow execution. Those paths used to be easy to treat as separate products. They are not separate trust boundaries.
      </p>
      <p>
        Gravitre derives write authority from the connector action catalog, not from string-matching action names in a blog post or a single workflow template. Chat and ReAct use{" "}
        <code>react_write_gate</code> and <code>chat_connector_execution_service</code>. Canvas runs use{" "}
        <code>canvas_write_gate</code> with the same catalog floor.
      </p>
      <p>
        Production re-verification for canvas (STA-322, July 2026) exercised a write with org policy requiring one approval. Execute returned{" "}
        <strong>pending_approval</strong>, the run row matched, and audit showed <strong>zero</strong>{" "}
        <code>tool.invoke.completed</code> events before approval. That is the bar we hold ourselves to: a gated write must not leak execution because the path was canvas instead of chat.
      </p>
      <p>
        In-graph human approval nodes (STA-323) normalize <code>human_approval</code> in workflow definitions so builder templates pause for approval instead of completing silently. Unit tests and live smokes cover hydration; async worker timing can still mean HTTP execute returns <code>running</code> before the local process reaches <code>awaiting_approval</code>. The guarantee is in the gate and run state, not in instant UI polish.
      </p>
      <p>
        For the full security framing (least privilege, OAuth, when we found our own gap), see our{" "}
        <Link href="/blog/security-first-approach">security-first write-authority post</Link>.
      </p>

      <h2>Who approves, and what members see</h2>
      <p>
        Write approval is not a settings toggle a power user can disable for one template. It is structural.
      </p>
      <ul>
        <li>
          <strong>Admin or owner (or an HITL policy approver)</strong> sees a confirm step in chat when policy allows them to approve the write locally.
        </li>
        <li>
          <strong>Members without approve permission</strong> still initiate requests. The panel shows: &ldquo;Your request will be sent for approval.&rdquo; The write queues in the Decision Queue at{" "}
          <Link href="/approvals">/approvals</Link>.
        </li>
        <li>
          <strong>Org policy</strong> is configurable at <Link href="/settings/approvals">Settings → Approvals</Link> (scope, action kinds, approver roles and named users).
        </li>
      </ul>
      <p>
        Orchestrated multi-step runs label each step as read (auto) or needs approval (write) before execution. That is visible in the pending task preview, not hidden until something breaks in a connected app.
      </p>

      <h2>Verified output, not performative success</h2>
      <p>
        A green checkmark that links nowhere teaches users to distrust the product. On the chat write path, Gravitre enforces{" "}
        <code>assert_execution_result_verifiable</code>: a successful write must include a non-empty summary body or a{" "}
        <code>result_url</code> deep link to the created or updated record.
      </p>
      <p>
        The execution panel states which case you got:
      </p>
      <ul>
        <li>
          <strong>Verified</strong> when a deep link is present (open the result link).
        </li>
        <li>
          <strong>Completed with inline summary only</strong> when the connector returned text but no URL (allowed on some verified batches by design).
        </li>
        <li>
          <strong>Failed with unverifiable_output</strong> when neither is present. No silent success.
        </li>
      </ul>
      <p>
        We do not claim every connector action in the catalog returns a deep link. Read actions and a large verified-write allowlist may legitimately omit <code>result_url</code>. The guarantee applies to the chat write enforcement path we test and expand batch by batch, not to a hand-wave that every integration behaves like Apollo list create or HubSpot record update.
      </p>

      <h2>Assumptions, labeled narrowly today</h2>
      <p>
        When Gravitre infers a connector plan field instead of reading it from your message, successful runs can include an <strong>Assumptions</strong> block in the execution panel. Backend code builds <code>assumption_notes</code> from <code>inferred_fields</code> and inference sources on the plan.
      </p>
      <p>
        The best-tested path today is omit-name creates (for example Apollo list create defaulting a list name). That is real, user-visible, and distinct from the success summary. It is not yet a full map of every model assumption on every action. We would rather show a narrow label honestly than imply full chain-of-thought exposition we have not built.
      </p>

      <h2>Recommendations with reasons, not execute buttons</h2>
      <p>
        The heuristic recommendation engine (STA-314) on <Link href="/intelligence">Intelligence</Link> suggests next steps such as connecting an unused integration or installing a pack prerequisite. Each card carries a <code>kind</code>, a human-readable <code>reason</code>, an <code>evidence</code> object, and <code>advisoryOnly: true</code>. There is no Execute surface on those cards by design (enforced in tests).
      </p>
      <p>
        We do not expose a formal <code>reason_code</code> enum in the API. If you need audit-friendly taxonomy, use <code>kind</code> plus the evidence payload today. Black-box scores without explanation are what we refused to ship.
      </p>

      <h2>Sources checked: real citations or an honest fallback</h2>
      <p>
        After knowledge-base tool runs, chat renders numbered citations with titles and links when <code>searchKnowledgeBase</code> returns results. When search returns nothing, the UI shows a <strong>Sources checked</strong> link to <Link href="/sources">/sources</Link>, not a fabricated citation list.
      </p>
      <p>
        That gap is intentional honesty. Claiming source attribution is solved would contradict the product behavior on empty search hits. Tool runs also append <strong>View audit trail</strong> and a control help link on every invocation block so operators know where to inspect events.
      </p>

      <h2>Audit trails: present, with known seams</h2>
      <p>
        Gravitre writes audit events server-side and exposes <Link href="/audit">/audit</Link> with filters plus CSV and JSON export. Chat links operators to that page after tool activity.
      </p>
      <p>
        Three seams worth knowing for incident review:
      </p>
      <ol className="mt-4 list-decimal space-y-2 pl-6">
        <li>The UI list/export path reads <code>audit_logs</code>; high-volume tool events also land in <code>audit_events</code>. Dual-write failures are logged as gaps, not silently dropped from ops awareness.</li>
        <li>Full audit log access is a plan-gated feature (<code>audit_logs</code> entitlement).</li>
        <li>Export capability in permissions is admin-oriented; the page UI does not hide export buttons by role today.</li>
      </ol>
      <p>
        We describe audit as <strong>partial but real</strong>, not as a perfect immutable ledger across every table and tier.
      </p>

      <h2>What we are still building toward</h2>
      <p>
        Broader assumption labeling across all write types, tighter audit read unification, and richer citation coverage when knowledge search misses are on the roadmap. They are not in this post as present-tense promises.
      </p>
      <p>
        Transparency, for us, is provable mechanics: catalog-backed approval, verifiable outputs on the write paths we enforce, explicit queue copy for members, advisory recommendations with evidence objects, and honest gaps where the product still falls short. That is the standard we use before any sentence reaches the marketing site.
      </p>
      <p>
        Configure approvals in <Link href="/settings/approvals">Settings</Link>, review queued writes in{" "}
        <Link href="/approvals">Approvals</Link>, and inspect events in <Link href="/audit">Audit</Link>. If you want the department-level metrics story (what we measure vs what we do not), read{" "}
        <Link href="/blog/measuring-what-ai-changes">Measuring What AI Actually Changes</Link>.
      </p>
    </>
  ),
}
