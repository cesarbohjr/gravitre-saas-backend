import type { ReactNode } from "react"
import type { BlogPost } from "../types"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

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
      <div className="mt-2 space-y-2 text-base leading-relaxed text-zinc-700">{children}</div>
    </div>
  )
}

function BlogFigure({
  src,
  alt,
  caption,
}: {
  src: string
  alt: string
  caption: string
}) {
  return (
    <figure className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} width={1200} height={675} className="w-full object-cover object-top" />
      <figcaption className="border-t border-zinc-200 px-4 py-3 text-sm text-zinc-600">{caption}</figcaption>
    </figure>
  )
}

export const workflowTemplatesPost: BlogPost = {
  slug: "workflow-templates-library",
  title: "Introducing 60+ Marketplace templates and department packs",
  description:
    "Gravitre Marketplace ships 60+ starter assets — workflow templates, department packs, agents, and knowledge — with connector checks before install and human approval on writes.",
  excerpt:
    "Most automation projects die before they ship. Not because the tech is wrong. Because the starting point is. Gravitre's Marketplace template library fixes that.",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  datePublished: "2026-03-21",
  dateModified: "2026-07-15",
  displayDate: "March 21, 2026",
  readTime: "12 min read",
  heroImage: "/images/blog/workflow-templates-hero.jpg",
  heroGradient: "from-amber-50 via-white to-emerald-50",
  heroAlt:
    "Gravitre Marketplace department packs grid showing Customer Success, Support Operations, and other installable packs with connector readiness.",
  keywords: [
    "workflow templates",
    "automation marketplace",
    "department packs",
    "RevOps workflows",
    "sales automation templates",
    "AI operations",
    "Gravitre Marketplace",
  ],
  takeaways: [
    "A Gravitre Marketplace asset is installable product: workflows, agents, knowledge, or a department pack that bundles them — not a blank canvas.",
    "The starter library has 60+ catalog assets, including 19 workflow templates and 6 department packs across sales, marketing, support, HR, finance, operations, and more.",
    "Every asset runs against the same connector catalog every Gravitre action uses. No one-off scripts per template.",
    "Install after a readiness check: missing connectors and permissions show up before install, not mid-run.",
    "Write actions are governed by org approval policy and platform write gates. Templates do not invent a parallel approval system.",
  ],
  faqs: [
    {
      question: "What is a Gravitre workflow template?",
      answer:
        "An installable Marketplace workflow with pre-built steps and declared connector dependencies. Department packs go further: they bundle agents, workflows, and knowledge for a function in one install.",
    },
    {
      question: "Do installed templates update automatically?",
      answer:
        "No. Browse and install from the catalog when you are ready. Org-owned assets you publish yourself support version history and rollback in org admin. Platform catalog installs are managed from Installed — they do not silently auto-update under you.",
    },
    {
      question: "What if I am missing a connector?",
      answer:
        "Before install, Gravitre runs an install check against required connectors. Missing apps show on the asset page with Connect links — including which ones are required vs optional — so you do not discover gaps mid-run.",
    },
    {
      question: "Can an approval step get skipped?",
      answer:
        "Write actions are gated by org Approvals policy and platform write authority derived from the action catalog — not by hoping each template remembered to add a gate. Review Approvals for write steps after install. We publish guarantees only for paths we have verified in production.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>Stop building from scratch. Start from what works.</strong>
      </p>
      <p>
        Most automation projects die before they ship. Not because the tech is wrong. Because the starting point is. A
        blank canvas feels like freedom. In practice, it is a reason to delay, over-build, and quietly abandon something
        that should have taken an afternoon.
      </p>
      <p>
        Gravitre&apos;s{" "}
        <Link href="/marketplace">Marketplace</Link> fixes that:{" "}
        <strong>60+ starter catalog assets</strong> — including <strong>19 workflow templates</strong> and{" "}
        <strong>6 department packs</strong> — plus agents and knowledge packs, organized by department, ready to install
        and run. Minutes, not weeks.
      </p>
      <p>
        Here is what is in the library today, how install actually works, and where we are honest about what is still
        hardening.
      </p>

      <h2>What a template actually is</h2>
      <p>Not a mockup. Not a skeleton you rebuild. In Marketplace terms, you will install one of:</p>
      <ul>
        <li>
          <strong>Workflow templates</strong> — executable sequences of actions and conditions with declared connector
          requirements.
        </li>
        <li>
          <strong>Department packs</strong> — a single install that bundles agents, workflows, and knowledge for a
          business function (for example Revenue Operations or Customer Success).
        </li>
        <li>
          <strong>Agents and knowledge packs</strong> — the building blocks packs assemble, also browsable on their own.
        </li>
      </ul>
      <p>
        Packs are often the fastest path: one card shows what is included, which apps you need, and whether you are
        ready to install.
      </p>

      <BlogFigure
        src="/images/blog/workflow-templates-marketplace-packs.jpg"
        alt="Marketplace Department packs filter showing Customer Success Pack, Support Operations Pack, and department facets."
        caption="Browse Department packs in Marketplace — filter by department, price, and readiness before you open Details."
      />

      <p>
        Browse the full catalog at{" "}
        <Link href="/marketplace/assets">/marketplace/assets</Link>. Prefer packs? Filter{" "}
        <Link href="/marketplace/assets?type=department_pack">Department packs</Link>. Prefer bare workflows? Filter{" "}
        <Link href="/marketplace/assets?type=workflow">Workflows</Link>. Step-by-step install guidance lives in the{" "}
        <Link href="/docs/guides/how-to/marketplace">Marketplace how-to</Link> and the{" "}
        <Link href="/docs/concepts/marketplace">Marketplace concepts</Link> doc.
      </p>

      <h2>Where the real guarantee lives</h2>
      <p>
        Every write action Gravitre takes — a CRM update, a ticket change, a document send — is checked against org
        Approvals policy and platform write authority derived from the action catalog. That check does not live as a
        one-off setting inside a single blog-listed template. It sits underneath writes, whether they started in chat or
        in a workflow run.
      </p>
      <p>
        After you install, review{" "}
        <Link href="/docs/guides/how-to/marketplace">Approvals for write steps</Link> on the workflow you deployed. We
        do not claim every seed workflow embeds a visible &ldquo;approval node&rdquo; in its graph. We do claim writes
        are not supposed to bypass the platform gates — and when we find a gap on a path (including canvas), we fix it
        and only then call it done. See also our{" "}
        <Link href="/blog/security-first-approach">security-first write-authority post</Link>.
      </p>

      <h2>The library (what ships today)</h2>
      <p>
        Counts below are the Gravitre starter catalog — real slugs in the Marketplace seed, not a roadmap wishlist.
        Department facets in the UI (Sales, Finance, HR, Security, Executive, and more) help you browse; the six
        department packs are the bundled &ldquo;install the outcome&rdquo; entry points.
      </p>

      <h3>Department packs</h3>
      <ul>
        <li>
          <strong>Revenue Operations Pack</strong> — RevOps + Sales Pipeline + CFO agents, Executive Summary workflow,
          RevOps knowledge.
        </li>
        <li>
          <strong>Marketing Operations Pack</strong> — multi-agent marketing production and handoffs.
        </li>
        <li>
          <strong>Customer Success Pack</strong> — CS agent, health monitoring workflow, CS knowledge.
        </li>
        <li>
          <strong>Support Operations Pack</strong> — ticket triage agent, support knowledge, optional SLA escalation
          (paid tier available).
        </li>
        <li>
          <strong>HR Operations Pack</strong> — people-ops agents and onboarding checklist workflow.
        </li>
        <li>
          <strong>MSP Operations Pack</strong> — MSP-oriented agents, workflows, and knowledge.
        </li>
      </ul>

      <h3>Sales and revenue operations</h3>
      <TemplateEntry title="HubSpot Lead Qualification">
        <p>Scores and qualifies inbound HubSpot leads against your ICP signals before routing.</p>
        <p>
          <em>Connects:</em> HubSpot. Open in catalog:{" "}
          <Link href="/marketplace/assets/hubspot-lead-qualification">hubspot-lead-qualification</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Lead Routing Automation">
        <p>Routes qualified leads to the right owner with CRM updates and team notification patterns.</p>
        <p>
          <em>Connects:</em> CRM + collaboration tools declared on the asset.{" "}
          <Link href="/marketplace/assets/lead-routing-automation">lead-routing-automation</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Salesforce Pipeline Review">
        <p>Pipeline review workflow for Salesforce-backed RevOps rituals.</p>
        <p>
          <Link href="/marketplace/assets/salesforce-pipeline-review">salesforce-pipeline-review</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Deal Desk Approval Flow">
        <p>Structured deal-desk path for pricing and exception review before a deal moves forward.</p>
        <p>
          <Link href="/marketplace/assets/deal-desk-approval-flow">deal-desk-approval-flow</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Executive Summary Generation">
        <p>Produces an executive-ready summary from connected RevOps context (included in the RevOps pack).</p>
        <p>
          <Link href="/marketplace/assets/executive-summary-generation">executive-summary-generation</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Weekly Team Status Report">
        <p>
          Scheduled team status digest — the closest starter to a &ldquo;weekly business digest&rdquo; for operators
          who want a Monday-ready rollup.
        </p>
        <p>
          <Link href="/marketplace/assets/weekly-team-status-report">weekly-team-status-report</Link>.
        </p>
      </TemplateEntry>

      <h3>Marketing operations</h3>
      <TemplateEntry title="Marketing Campaign Production">
        <p>Campaign production workflow wired to marketing agents and connectors.</p>
        <p>
          <Link href="/marketplace/assets/marketing-campaign-production">marketing-campaign-production</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Marketing Attribution Analysis">
        <p>Attribution analysis across campaign and CRM signals.</p>
        <p>
          <Link href="/marketplace/assets/marketing-attribution-analysis">marketing-attribution-analysis</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Campaign Performance Digest">
        <p>Recurring campaign performance digest for marketing ops.</p>
        <p>
          <Link href="/marketplace/assets/campaign-performance-digest">campaign-performance-digest</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Competitive Intelligence Monitoring">
        <p>Ongoing competitive monitoring workflow.</p>
        <p>
          <Link href="/marketplace/assets/competitive-intelligence-monitoring">
            competitive-intelligence-monitoring
          </Link>
          .
        </p>
      </TemplateEntry>

      <h3>Customer support and success</h3>
      <TemplateEntry title="Zendesk Ticket Triage">
        <p>Classifies and routes Zendesk tickets using the support triage agent patterns.</p>
        <p>
          <Link href="/marketplace/assets/zendesk-ticket-triage">zendesk-ticket-triage</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Customer Health Monitoring">
        <p>Watches account health signals and surfaces risk for CSMs.</p>
        <p>
          <Link href="/marketplace/assets/customer-health-monitoring">customer-health-monitoring</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="QBR Preparation Workflow">
        <p>Assembles QBR prep inputs so the meeting is not a scavenger hunt.</p>
        <p>
          <Link href="/marketplace/assets/qbr-preparation-workflow">qbr-preparation-workflow</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="SLA Breach Escalation">
        <p>Escalates when SLA thresholds are at risk or breached.</p>
        <p>
          <Link href="/marketplace/assets/sla-breach-escalation">sla-breach-escalation</Link>.
        </p>
      </TemplateEntry>

      <h3>HR, finance, product, and security</h3>
      <TemplateEntry title="New Hire Onboarding Checklist">
        <p>Checklist-driven onboarding workflow for people ops.</p>
        <p>
          <Link href="/marketplace/assets/new-hire-onboarding-checklist">new-hire-onboarding-checklist</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Invoice Exception Review">
        <p>Flags invoice exceptions for finance review.</p>
        <p>
          <Link href="/marketplace/assets/invoice-exception-review">invoice-exception-review</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Monthly Executive Reporting">
        <p>Monthly executive reporting package from connected systems.</p>
        <p>
          <Link href="/marketplace/assets/monthly-executive-reporting">monthly-executive-reporting</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Product Feedback Synthesis">
        <p>Synthesizes product feedback for ops and product partners.</p>
        <p>
          <Link href="/marketplace/assets/product-feedback-synthesis">product-feedback-synthesis</Link>.
        </p>
      </TemplateEntry>
      <TemplateEntry title="Security Access Review">
        <p>Access review workflow for security and compliance rituals.</p>
        <p>
          <Link href="/marketplace/assets/security-access-review">security-access-review</Link>.
        </p>
      </TemplateEntry>

      <h2>How templates get maintained</h2>
      <p>
        Catalog assets are versioned in the Marketplace data model. If you{" "}
        <Link href="/docs/guides/how-to/marketplace-publish">publish org-owned assets</Link>, version history and
        rollback are available to org admins. Gravitre platform catalog installs do not silently rewrite themselves
        under you — you install deliberately, and you manage what is deployed from{" "}
        <Link href="/marketplace/installed">Installed</Link>.
      </p>
      <p>
        When a connector API or pack improves, we ship catalog updates. You decide when to install the newer asset.
        That is slower than auto-update — and safer for production ops.
      </p>

      <h2>Installing one</h2>
      <p>Three practical steps — matching the product, not a brochure:</p>
      <ol className="mt-4 list-decimal space-y-2 pl-6">
        <li>
          <strong>Preview.</strong> Open the asset (or pack) detail page. Read description, what&apos;s included, and
          required apps. Packs show agents, workflows, and knowledge in one list.
        </li>
        <li>
          <strong>Connect.</strong> Gravitre runs an install check against connectors you already have. Missing
          required apps block install and show Connect links — before anything is deployed.
        </li>
        <li>
          <strong>Install.</strong> Confirm install (purchase first if the asset is paid). Open the deployed workflow or
          agents from the success state or{" "}
          <Link href="/marketplace/installed">Installed</Link>. Configure environment-specific details on the deployed
          assets as needed.
        </li>
      </ol>

      <BlogFigure
        src="/images/blog/workflow-templates-install-connectors.jpg"
        alt="Revenue Operations Pack detail showing HubSpot and Salesforce required connector blockers and what's included."
        caption="Install check on Revenue Operations Pack — required CRM connectors block install until connected; what's included lists agents, workflow, and knowledge."
      />

      <p>
        Catalog cards also show readiness pills like <strong>N/M apps connected</strong> so you see gaps before you even
        open Details. Connect integrations from{" "}
        <Link href="/connectors">/connectors</Link> or follow{" "}
        <Link href="/docs/guides/how-to/connectors">Connect integrations</Link>.
      </p>
      <p>
        Bookmark candidates with Save, then review them under{" "}
        <Link href="/marketplace/saved">Saved</Link> before you install.
      </p>

      <h2>What templates don&apos;t do</h2>
      <p>Worth saying plainly.</p>
      <p>
        Every org&apos;s data model is a little different. Your deal stages are not named the same as anyone else&apos;s.
        Install gets you the sequence and connector wiring; you still own environment configuration, Approvals policy,
        and the last mile of naming. Some workflows need tweaking after install. Expected.
      </p>
      <p>
        What templates kill is the blank-page problem. The sequence is designed. The connectors are declared. The
        platform write gates still apply. You are configuring and governing — not architecting from zero.
      </p>

      <h2>Where to start</h2>
      <p>
        Filter by department, asset type, or price in{" "}
        <Link href="/marketplace/assets">Marketplace → Assets</Link>.
      </p>
      <p>
        Not sure? Start with the <strong>Revenue Operations Pack</strong> if you live in CRM, or{" "}
        <strong>Weekly Team Status Report</strong> if you want a lightweight scheduled digest. Ten minutes of connect +
        install beats a month of whiteboard architecture.
      </p>
      <p>
        Browse the library in the <Link href="/marketplace">Gravitre Marketplace</Link>. Install walkthrough:{" "}
        <Link href="/docs/guides/how-to/marketplace">Install from the Marketplace</Link>. Publish your own:{" "}
        <Link href="/docs/guides/how-to/marketplace-publish">Publish Marketplace assets</Link>.
      </p>
    </>
  ),
}
