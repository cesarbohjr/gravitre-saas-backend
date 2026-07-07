import type { ReactNode } from "react"
import type { BlogPost } from "../types"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"

function TemplateEntry({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="mt-6 border-t border-zinc-100 pt-6 first:mt-0 first:border-t-0 first:pt-0">
      <h4 className="text-lg font-semibold text-zinc-900">{title}</h4>
      <div className="mt-2 space-y-2">{children}</div>
    </div>
  )
}

export const workflowTemplatesPost: BlogPost = {
  slug: "workflow-templates-library",
  title: "Introducing 50+ Pre-Built Workflow Templates",
  description:
    "50+ pre-built Gravitre workflow templates across seven departments — executable workflows with connectors, agent assignments, and approval gates. Install in minutes, not weeks.",
  excerpt:
    "Most workflow automation projects fail before they ship — not because the technology is wrong, but because the starting point is wrong. Gravitre's template library fixes that.",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  datePublished: "2026-03-21",
  dateModified: "2026-07-05",
  displayDate: "March 21, 2026",
  readTime: "16 min read",
  heroImage: "",
  heroGradient: "from-amber-50 via-white to-emerald-50",
  heroAlt: "Grid of workflow cards representing pre-built automation templates.",
  keywords: [
    "workflow templates",
    "automation marketplace",
    "RevOps workflows",
    "sales automation templates",
    "AI operations",
    "workflow automation library",
    "Gravitre Marketplace",
  ],
  takeaways: [
    "A Gravitre template is a fully specified, executable workflow — not a skeleton — with steps, connectors, agent assignments, and approval gates already built.",
    "50+ templates span seven departments: sales, marketing, support, HR, finance, engineering, and executive ops.",
    "Templates are versioned in the Marketplace; updates are visible and rollbacks are always available.",
    "Install in three steps: preview, connect tools, fill configuration variables — with missing connectors surfaced before installation.",
    "Templates eliminate starting-from-zero; you configure org-specific values, not architect entire workflows from scratch.",
  ],
  faqs: [
    {
      question: "What is a Gravitre workflow template?",
      answer:
        "A fully specified, executable workflow with pre-configured steps, defined connector dependencies, agent assignments, approval gates, and configuration variables you fill in at install time — not a visual mockup or blank skeleton.",
    },
    {
      question: "Do installed templates update automatically?",
      answer:
        "No. Templates are versioned in the Marketplace. When an update is published, you see what changed and apply it when you are ready. Prior versions remain accessible for rollback.",
    },
    {
      question: "What if I am missing a connector?",
      answer:
        "Before installation, Gravitre checks which connectors the template requires and which are already connected. Missing connectors are shown with the exact permissions needed — you do not discover gaps after install.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>Stop building from scratch. Start from what works.</strong>
      </p>
      <p>
        Most workflow automation projects fail before they ship.
      </p>
      <p>
        Not because the technology is wrong. Because the starting point is wrong. A blank canvas sounds like freedom. In
        practice it is a reason to delay, over-engineer, and eventually abandon something that should have taken an
        afternoon.
      </p>
      <p>
        Gravitre&apos;s template library fixes that. 50+ pre-built workflow templates, organized by department, ready to
        install, configure, and run — in minutes, not weeks.
      </p>
      <p>
        Here is what is in the library, how it is organized, and why it is built the way it is.
      </p>

      <h2>What a Template Actually Is</h2>
      <p>
        Before getting into the specifics, it is worth being precise about what a Gravitre template is — because
        &quot;template&quot; means different things in different tools.
      </p>
      <p>
        In Gravitre, a template is not a visual mockup or a starting skeleton you rebuild from scratch. It is a fully
        specified, executable workflow with:
      </p>
      <ul>
        <li>
          <strong>Pre-configured steps</strong> — the sequence of actions, conditions, and logic the workflow executes
        </li>
        <li>
          <strong>Defined connector dependencies</strong> — the specific integrations the workflow needs to run
          (HubSpot, Slack, Google Workspace, etc.)
        </li>
        <li>
          <strong>Agent assignments</strong> — which AI agent handles each step, with the relevant persona and
          permissions already set
        </li>
        <li>
          <strong>Approval gates</strong> — built in at the steps where human review is required, not bolted on later
        </li>
        <li>
          <strong>Variables and configuration hooks</strong> — the org-specific values you fill in at install time
          (pipeline stage names, folder paths, team member identifiers)
        </li>
      </ul>
      <p>
        Install a template, connect your tools, fill in the variables. The workflow is ready to run.
      </p>
      <p>
        Templates in Gravitre live in the Marketplace — the same place you find department packs, AI agents, and
        knowledge bases. They are versioned, maintained, and auditable. If a template is updated, you see the change. If
        something breaks, you can roll back.
      </p>

      <h2>The Library at a Glance</h2>
      <p>
        50+ templates across seven departments. Every template is built against real connector data — not hypothetical
        integrations, but the specific APIs and data models of the tools your teams actually use.
      </p>

      <h3>Sales and Revenue Operations</h3>

      <TemplateEntry title="Lead Qualification and Routing">
        <p>
          New leads from HubSpot or Salesforce are scored against your ICP criteria, enriched with company data, and
          routed to the right rep — with a Slack notification and a CRM record updated automatically.
        </p>
        <p>
          <strong>What it connects:</strong> HubSpot or Salesforce, Slack, Apollo (optional enrichment)
        </p>
        <p>
          <strong>Approval gate:</strong> High-value leads above a configurable threshold route to a manager for review
          before assignment.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Deal Health Monitor">
        <p>
          Monitors your open pipeline for deals that have gone quiet. Detects: no activity in N days, no next step
          logged, contact not engaged since last touchpoint. Surfaces them in Slack and creates a task for the owning
          rep.
        </p>
        <p>
          <strong>What it connects:</strong> HubSpot or Salesforce, Slack
        </p>
        <p>
          <strong>No approval required</strong> — this is read-only detection with a notification output.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Renewal Risk Alert">
        <p>
          Checks subscriptions approaching renewal date against engagement signals — support ticket volume, login
          frequency, NPS responses if available. Flags accounts showing risk signals 60 and 30 days out.
        </p>
        <p>
          <strong>What it connects:</strong> Stripe, HubSpot or Salesforce, Zendesk or Intercom (optional)
        </p>
        <p>
          <strong>Output:</strong> A prioritized list of at-risk renewals with the specific signals that triggered each
          flag. Not a guess. Evidence.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Proposal and Quote Automation">
        <p>
          When a deal reaches a configured stage, pulls the relevant account data, product configuration, and pricing
          from your CRM, generates a draft proposal, and routes it for human review before sending.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before any document is sent. The workflow stops here until a human
          approves.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Win/Loss Analysis">
        <p>
          When a deal is closed — won or lost — collects the available signals, categorizes the outcome against
          configurable criteria, and updates your pipeline analytics. Identifies patterns across closed deals over
          time.
        </p>
        <p>
          <strong>What it connects:</strong> HubSpot or Salesforce, Google Sheets or Notion (optional output)
        </p>
      </TemplateEntry>

      <TemplateEntry title="Sales Performance Digest">
        <p>
          Weekly summary of pipeline activity, deal progression, and key metrics delivered to sales leadership. Pulls
          from CRM, compares against targets, flags variances.
        </p>
        <p>
          <strong>Output:</strong> Slack message or email, configurable schedule.
        </p>
      </TemplateEntry>

      <h3>Marketing Operations</h3>

      <TemplateEntry title="Campaign Launch Checklist">
        <p>
          Before a campaign goes live, verifies: UTM parameters are set, landing page is live and loads correctly,
          tracking pixels are firing, audience segments match the brief. Blocks launch if checks fail. Routes for
          approval when all checks pass.
        </p>
        <p>
          <strong>What it connects:</strong> Google Analytics, HubSpot, your CMS
        </p>
        <p>
          <strong>Approval gate:</strong> Required before campaign activation.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Lead Nurture Enrollment">
        <p>
          When a contact meets configured criteria — source, score, behavior — automatically enrolls them in the
          appropriate nurture sequence and tags them in your CRM.
        </p>
        <p>
          <strong>What it connects:</strong> HubSpot, Mailchimp or equivalent
        </p>
      </TemplateEntry>

      <TemplateEntry title="Content Performance Report">
        <p>
          Weekly pull of content performance data across channels. Organic traffic by page, conversion rate by content
          type, top and bottom performers. Delivered to the marketing team on a schedule.
        </p>
        <p>
          <strong>What it connects:</strong> Google Analytics, Google Search Console, HubSpot
        </p>
        <p>No manual pull required.</p>
      </TemplateEntry>

      <TemplateEntry title="SEO Monitoring Alert">
        <p>
          Monitors your top-performing pages for ranking changes, traffic drops, and indexing issues. Alerts immediately
          when a significant change is detected.
        </p>
        <p>
          <strong>What it connects:</strong> Google Search Console, Google Analytics
        </p>
        <p>Detection threshold is configurable. Default: 15% traffic drop week-over-week.</p>
      </TemplateEntry>

      <TemplateEntry title="Social Listening and Mention Routing">
        <p>
          Monitors brand mentions across configured channels, classifies them by sentiment and urgency, and routes
          high-priority mentions to the appropriate team member.
        </p>
        <p>
          <strong>Approval gate:</strong> Not required for monitoring. Required if the workflow drafts a response for
          posting.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Campaign Attribution Reconciliation">
        <p>
          Reconciles spend data from your ad platforms with conversion data from your CRM. Surfaces discrepancies,
          calculates cost per acquisition by channel, and flags campaigns where attributed revenue does not match spend
          expectations.
        </p>
        <p>
          <strong>What it connects:</strong> HubSpot, Google Ads, LinkedIn Ads, Stripe (optional)
        </p>
      </TemplateEntry>

      <h3>Customer Support and Success</h3>

      <TemplateEntry title="Ticket Triage and Priority Routing">
        <p>
          Incoming support tickets are classified by type, urgency, and account tier. High-value accounts and critical
          issues are escalated immediately. Routine tickets are routed to the appropriate queue.
        </p>
        <p>
          <strong>What it connects:</strong> Zendesk, Intercom, or Freshdesk; HubSpot or Salesforce for account tier
          data
        </p>
      </TemplateEntry>

      <TemplateEntry title="Escalation Detection">
        <p>
          Monitors active tickets for escalation signals — tone shift in customer messages, repeated contact on the same
          issue, mentions of cancellation or legal. Flags immediately to the customer success team.
        </p>
        <p>Detection is running continuously, not on a schedule.</p>
      </TemplateEntry>

      <TemplateEntry title="Churn Risk Response">
        <p>
          When a customer shows configured churn signals — reduced product usage, open tickets without resolution,
          missed check-in — triggers a response workflow: internal alert, account review task, and a drafted outreach
          message for human review and sending.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before any customer communication is sent.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Onboarding Completion Monitor">
        <p>
          Tracks new customers against their onboarding milestones. When a customer falls behind schedule, alerts the
          CSM and creates a check-in task.
        </p>
        <p>
          <strong>What it connects:</strong> Your CRM, your product analytics platform
        </p>
      </TemplateEntry>

      <TemplateEntry title="CSAT and NPS Follow-Up">
        <p>
          When a survey response comes in below a configured threshold, triggers a follow-up workflow: internal alert to
          the CSM, task creation, and a drafted response for review.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before response is sent.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Support Digest for Leadership">
        <p>
          Weekly summary of support volume, resolution times, escalation rate, and top issue categories. Delivered to CS
          leadership on a schedule.
        </p>
      </TemplateEntry>

      <h3>Human Resources</h3>

      <TemplateEntry title="Job Posting Distribution">
        <p>
          When a new role is approved in your ATS, distributes the posting to configured job boards, updates your
          careers page, and notifies the hiring team.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before any external posting is published.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Candidate Pipeline Monitor">
        <p>
          Tracks candidates moving through your hiring pipeline. Flags roles where candidate movement has stalled, stages
          where drop-off is high, and interviews that have not been scheduled within the configured window.
        </p>
        <p>
          <strong>What it connects:</strong> Your ATS (Greenhouse, Lever, or equivalent)
        </p>
      </TemplateEntry>

      <TemplateEntry title="Offer Letter Generation">
        <p>
          When a candidate reaches the offer stage, pulls compensation data, role details, and start date from your ATS
          and HR system, generates a draft offer letter, and routes it for approval before sending.
        </p>
        <p>
          <strong>Approval gate:</strong> Required. Offer letters do not send without explicit human approval.
        </p>
      </TemplateEntry>

      <TemplateEntry title="New Employee Onboarding">
        <p>
          On a new hire&apos;s start date, triggers the onboarding sequence: system access requests, welcome message,
          onboarding task assignment, manager notification, and equipment provisioning request.
        </p>
        <p>
          <strong>What it connects:</strong> Google Workspace or Microsoft 365, Slack, your HRIS
        </p>
      </TemplateEntry>

      <TemplateEntry title="PTO and Leave Tracking">
        <p>
          Monitors leave requests against team capacity and policy. Flags conflicts, routes approvals to the appropriate
          manager, and updates team calendars when approved.
        </p>
        <p>
          <strong>Approval gate:</strong> Required from manager before leave is confirmed.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Performance Review Reminder">
        <p>
          Monitors review cycles and sends reminders to managers and employees as deadlines approach. Tracks completion
          status and escalates overdue reviews.
        </p>
      </TemplateEntry>

      <h3>Finance and Operations</h3>

      <TemplateEntry title="Invoice Processing">
        <p>
          Incoming invoices are extracted, validated against purchase orders, and routed for approval based on
          configurable amount thresholds. Small invoices below the threshold are auto-approved. Large invoices route to
          finance leadership.
        </p>
        <p>
          <strong>Approval gate:</strong> Required for invoices above configured threshold. The threshold is set by your
          team, not by Gravitre.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Expense Report Review">
        <p>
          Expense reports are checked against policy — receipt attached, category correct, amount within limits.
          Out-of-policy submissions are flagged and returned with the specific issue identified.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Revenue Recognition Reconciliation">
        <p>
          Reconciles subscription revenue from Stripe against your accounting system. Flags discrepancies, deferred
          revenue items, and recognition timing issues.
        </p>
        <p>
          <strong>What it connects:</strong> Stripe, QuickBooks or Xero
        </p>
      </TemplateEntry>

      <TemplateEntry title="Budget vs. Actual Alert">
        <p>
          Monitors departmental spend against budget. When a department approaches or exceeds its threshold, alerts the
          budget owner and finance team. Configurable alert levels: 80%, 90%, 100%.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Vendor Contract Renewal">
        <p>
          Monitors active vendor contracts against renewal dates. Surfaces contracts approaching expiration 90, 60, and
          30 days out with the contract value and owner identified.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Financial Close Checklist">
        <p>
          Guides the monthly close process through a configured sequence of tasks. Tracks completion, routes approvals,
          and surfaces blockers to the finance team.
        </p>
      </TemplateEntry>

      <h3>Engineering and Product</h3>

      <TemplateEntry title="Incident Response">
        <p>
          When a critical alert fires — PagerDuty, Datadog, or equivalent — triggers the incident response workflow:
          channel creation in Slack, on-call notification, status page update, and stakeholder communication draft.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before external status page is updated or stakeholder communication
          is sent.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Pull Request Review Reminder">
        <p>
          Monitors open PRs for review lag. When a PR has been waiting for review beyond the configured threshold, sends
          a reminder to the assigned reviewer and surfaces it in the team standup digest.
        </p>
        <p>
          <strong>What it connects:</strong> GitHub, Slack
        </p>
      </TemplateEntry>

      <TemplateEntry title="Deployment Notification">
        <p>
          When a deployment completes, sends a structured notification to configured channels with the deployment
          details, link to the diff, and on-call contact for the release window.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Sprint Planning Data Pull">
        <p>
          Before sprint planning, pulls relevant data: open bugs by priority, items carried over from the previous
          sprint, velocity trend, and backlog items flagged for this cycle. Delivered to the team before the meeting.
        </p>
        <p>
          <strong>What it connects:</strong> Jira or Linear, Confluence or Notion (optional)
        </p>
      </TemplateEntry>

      <TemplateEntry title="On-Call Rotation Handoff">
        <p>
          At the scheduled handoff time, generates a summary of active incidents, recent alerts, and open items for the
          incoming on-call engineer. Delivered via Slack and email.
        </p>
      </TemplateEntry>

      <h3>Executive and Cross-Functional</h3>

      <TemplateEntry title="Weekly Business Digest">
        <p>
          A structured weekly summary of the metrics that matter to leadership — pipeline, revenue trend, support
          volume, team capacity, and flagged risks. Delivered every Monday morning before the leadership meeting.
        </p>
        <p>Pulls from every connected system. No manual assembly required.</p>
      </TemplateEntry>

      <TemplateEntry title="OKR Progress Report">
        <p>
          Monitors key result progress against targets. Flags objectives falling behind, surfaces supporting data, and
          delivers a progress summary to the leadership team on a configured schedule.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Cross-Department Approval Queue">
        <p>
          Consolidates approval requests from across departments — invoices, offers, campaigns, content, deployments —
          into a single queue for the relevant approvers. One place. No inbox archaeology.
        </p>
      </TemplateEntry>

      <TemplateEntry title="Board Report Data Package">
        <p>
          Pulls the data required for board reporting — revenue, growth, pipeline, headcount, key metrics — formats it
          into a structured package, and routes it to the executive team for review before the board meeting.
        </p>
        <p>
          <strong>Approval gate:</strong> Required before package is distributed externally.
        </p>
      </TemplateEntry>

      <h2>How Templates Are Maintained</h2>
      <p>
        Templates in the Gravitre Marketplace are versioned. When a connector API changes, when a best practice shifts,
        or when a template is improved based on usage patterns, the update is published with a version number.
      </p>
      <p>
        Your installed templates do not update automatically. You see that an update is available, you review what
        changed, and you apply it when you are ready.
      </p>
      <p>
        If an update breaks something, you can roll back. The prior version is always accessible.
      </p>

      <h2>Installing a Template</h2>
      <p>Three steps.</p>
      <ol className="mt-4 list-decimal space-y-4 pl-6">
        <li>
          <strong>Browse and preview.</strong> Every template in the Marketplace includes the full workflow diagram, the
          connector dependencies, the approval gates, and a list of the configuration variables you will need to fill
          in. Review it before you install.
        </li>
        <li>
          <strong>Connect your tools.</strong> Gravitre checks which connectors the template requires and which ones are
          already connected for your organization. If a connector is missing, you are shown exactly which one and what
          permissions it needs. You do not discover a missing connection after installation.
        </li>
        <li>
          <strong>Fill in your variables.</strong> Pipeline stage names. Folder paths. Team member identifiers. Amount
          thresholds. The template asks for exactly what it needs. Nothing more.
        </li>
      </ol>
      <p>
        After installation, the workflow is live and ready to run. You can test it, modify it, or run it exactly as
        configured. It is yours.
      </p>

      <h2>What Templates Do Not Do</h2>
      <p>Worth being direct about this.</p>
      <p>
        Templates are starting points, not finished products. Every organization&apos;s data model is slightly different.
        Your deal stages have different names. Your approval thresholds are not the same as anyone else&apos;s. Your team
        structure is your own.
      </p>
      <p>
        Templates account for this through configuration variables. But they do not account for every edge case in every
        organization. Some workflows will need modification after installation. That is expected.
      </p>
      <p>
        What templates eliminate is the starting-from-zero problem. The sequence of steps is designed. The connector
        integrations are specified. The approval logic is built. You are configuring, not architecting.
      </p>
      <p>
        That is a meaningful difference in time, risk, and likelihood of actually shipping.
      </p>

      <h2>Finding the Right Template</h2>
      <p>
        The Marketplace has filtering by department, connector, and use case. If you know which department you are
        building for, start there.
      </p>
      <p>
        If you are not sure where to start, start with the <strong>Weekly Business Digest</strong>. It connects to
        every system you have already set up, surfaces the most important data from all of them, and delivers it to
        whoever needs it on a schedule.
      </p>
      <p>
        It takes about ten minutes to configure. The first time leadership gets the report without asking for it, the
        question of whether workflow automation is worth it tends to answer itself.
      </p>
      <p>
        Browse the full template library in the{" "}
        <a href="/marketplace">Gravitre Marketplace</a>. Questions about a specific template or connector? The{" "}
        <a href="/docs/guides/how-to/marketplace">Gravitre docs</a> have the details.
      </p>
    </>
  ),
}
