import type { BlogPost } from "../types"
import { createBlogDates } from "../blog-dates"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

export const measuringAiRoiPost: BlogPost = {
  slug: "measuring-what-ai-changes",
  title: "Measuring What AI Actually Changes",
  description:
    "Which department ROI numbers Gravitre computes today (signals, operational counts, labeled estimates) and which outcomes we do not measure yet — without before/after placeholders.",
  excerpt:
    "Department ROI is where AI marketing goes to die. Here is what Gravitre's dashboards and intelligence packs actually count, what is estimate-only, and what we refuse to print until ground-truth measurement ships.",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  ...createBlogDates("2026-07-17"),
  readTime: "8 min read",
  heroImage: "",
  heroGradient: "from-slate-50 via-emerald-50/40 to-zinc-100",
  heroAlt:
    "Dashboard panels showing operational counts and estimate labels, with empty slots for unmeasured business ROI.",
  keywords: [
    "AI ROI measurement",
    "department AI metrics",
    "intelligence packs KPIs",
    "AI automation ROI",
    "operational metrics vs estimates",
    "marketplace ROI",
    "AI governance metrics",
  ],
  takeaways: [
    "PackKpiPanel counts ingestion signals, entities, cache-linked rows, and install scaffolding — not cost per lead, pipeline dollars, or ticket MTTR.",
    "Intelligence Reports shows operational event counts and recommendation approval rate; hours saved, revenue influenced, and cost savings render as em dashes with insufficient_data until STA-289 ground truth ships.",
    "Marketplace catalog hours-saved figures are publisher estimates, explicitly labeled estimate-only per OUTCOME_ESTIMATE_LABELING — not measured time-on-task.",
    "MSP Intelligence Pack tracks NVD/CVE and CISA KEV signals when invoked; it does not compute PSA ticket resolution time.",
    "Sales prospecting packs document Apollo BYO plan limits honestly; discovery search may 403 on free tiers while list create paths work.",
    "Brief-style before/after hour or minute savings (40→10 hours, 30→20 minutes) have no customer pilot backing in this repo and must not be published as measured results without Cesar confirming real data.",
  ],
  faqs: [
    {
      question: "Does Gravitre show marketing cost per lead?",
      answer:
        "No computed CPL dashboard exists today. Marketing Intelligence Pack KPIs reflect Google Search Console ingestion counts when that connector runs, plus install counts. Campaign workflows and digests are scaffolds agents run; they are not automatic ROI math.",
    },
    {
      question: "Can I see sales pipeline or meetings booked in a pack KPI panel?",
      answer:
        "Not as platform-computed KPIs. HubSpot pipeline list and deal reads exist in Customer Success workflows. Sales and Prospecting intelligence packs have empty vendor maps in the KPI service, so signal counts stay zero until business-metric ingestion is built.",
    },
    {
      question: "What does Marketplace ROI analytics measure?",
      answer:
        "Catalog estimated_hours_saved multiplied by adoption heuristics (at least one adoption event). The page and OUTCOME_ESTIMATE_LABELING doc call this estimate-only, not a before/after study.",
    },
    {
      question: "When will hours saved be a real number?",
      answer:
        "STA-289 ground-truth measurement is deferred. Until it ships, Intelligence Reports keeps hours saved, revenue influenced, and cost savings as insufficient_data rather than fabricating trends.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>ROI posts fail when they confuse what the product counted with what a team hopes happened.</strong>
      </p>
      <p>
        Gravitre sells automation with governance. That same discipline applies to metrics: we separate operational telemetry, publisher estimates, and business outcomes we have not measured yet. This post maps department-level claims to what is live in code, what is partial, and what is not built. It deliberately omits before/after hour or minute savings unless and until real customer or pilot data exists to support them.
      </p>

      <h2>Open question for operators (before you trust any vendor’s ratios)</h2>
      <p>
        Brief-style examples like &ldquo;40 hours → 10 hours&rdquo; or &ldquo;30 minutes → 20 minutes&rdquo; read as illustrations, not measured Gravitre customer outcomes. We searched delivery artifacts, catalog metadata, and production telemetry hooks. <strong>No backing data exists in this repository.</strong> If you have pilot numbers, name the study before we ever print them on the marketing site. Until then, this post uses qualitative, mechanism-level framing only.
      </p>

      <h2>Three metric classes we actually use</h2>
      <p>
        Internal labeling (STA-286 / <code>OUTCOME_ESTIMATE_LABELING.md</code>) splits metrics into:
      </p>
      <ul>
        <li>
          <strong>Operational</strong> — events Gravitre recorded (workflow runs, connector actions, task job success rates). Counts activity in the product; does not prove business ROI.
        </li>
        <li>
          <strong>Estimate</strong> — catalog publisher metadata (for example est. hours saved on a marketplace workflow). Shown with estimate badges, not as measured savings.
        </li>
        <li>
          <strong>Deferred</strong> — time-on-task, before/after pilot ROI (STA-289). Surfaces show insufficient_data instead of fake precision.
        </li>
      </ul>
      <p>
        If a dashboard cell shows an em dash on Intelligence Reports, that is honesty, not a missing sprint.
      </p>

      <h2>What PackKpiPanel actually shows</h2>
      <p>
        Intelligence pack installs expose a <strong>Pack KPI</strong> panel (<code>PackKpiPanel</code>) with:
      </p>
      <ul>
        <li>Signals ingested</li>
        <li>Entities cached</li>
        <li>Cache-linked rows</li>
        <li>Agents, workflows, and assignments installed from the pack scaffold</li>
        <li>Per-vendor breakdown when the pack registers vendors in the KPI map</li>
      </ul>
      <p>
        That panel answers: <strong>Is this pack installed, and is its ingestion pipeline moving data?</strong> It does not answer: <strong>Did marketing cut agency spend or did support shave MTTR?</strong> Conflating those questions is how ROI content loses credibility.
      </p>

      <h2>Marketing</h2>
      <p>
        <strong>Verified today:</strong> Marketing Intelligence Pack ties KPI signals to Google Search Console when that connector is invoked. Marketing Operations Pack and campaign digest workflows are installable marketplace scaffolds (agents + workflows + declared connectors).
      </p>
      <p>
        <strong>Not built:</strong> content production time, cost per lead, campaign launch velocity as platform-computed KPIs. A pricing-page testimonial about campaign production time exists in code but is gated off (<code>SHOW_MARKETING_TESTIMONIALS = false</code>) and has no measurement pipeline.
      </p>
      <p>
        <strong>Estimate-only:</strong> Marketplace assets may carry <code>estimated_hours_saved</code> metadata used in ROI analytics math, labeled as publisher estimates.
      </p>

      <h2>Sales and revenue operations</h2>
      <p>
        <strong>Verified today:</strong> Apollo BYO plan-tier labeling and 403 plan-limit detection are live in connector copy and error handling. Prospecting discovery on restricted plans fails with an upgrade message instead of pretending full search works. List create and other verified write paths remain testable where entitled.
      </p>
      <p>
        <strong>Partial:</strong> HubSpot pipeline and deal list reads appear in Customer Success pack workflows. Revenue Operations pack bundles RevOps agents and an executive summary workflow scaffold.
      </p>
      <p>
        <strong>Not built:</strong> meetings booked counters, pipeline dollars generated, prospecting hours saved as dashboard KPIs. Sales and Prospecting intelligence packs register no KPI vendors today, so PackKpiPanel signal counts stay at zero for business metrics.
      </p>
      <p>
        Do not infer full outbound discovery from pack marketing copy without checking connector entitlement and Apollo plan tier. We label that limitation on purpose.
      </p>

      <h2>MSP and IT operations</h2>
      <p>
        <strong>Verified today:</strong> MSP Intelligence Pack ingests NVD/CVE and CISA KEV feeds when those tools run, with live install smokes and signal mappers. Pack KPIs reflect that ingestion volume.
      </p>
      <p>
        <strong>Not built:</strong> ticket resolution time, first-response SLA attainment, or PSA/RMM ticket-time rollups as computed KPIs. MSP Operations Pack weekly status workflow is an agent summarize → notify scaffold, not ticket timing math. Compliance scorecards beyond knowledge RAG are not computed dashboards.
      </p>

      <h2>Customer success and support</h2>
      <p>
        <strong>Partial:</strong> Customer Success pack workflows pull HubSpot deals and Zendesk ticket lists for agent-driven health review steps. Support Operations pack includes Zendesk triage agent patterns in the marketplace catalog.
      </p>
      <p>
        <strong>Not built:</strong> account health scores as CRM-field-derived KPIs. STA-124 integration health scores measure connector and platform readiness (Configured → Executable), not customer account health. ML churn risk models in the catalog are advisory, not a CS dashboard metric.
      </p>
      <p>
        Saying &ldquo;health monitoring workflow&rdquo; means an installable sequence with declared connectors, not a guaranteed health score widget unless we build and verify that computation separately.
      </p>

      <h2>Executive and finance-facing rollups</h2>
      <p>
        <strong>Verified today:</strong> Executive Intelligence Pack ingests macro/regulatory signals (FRED, SEC, World Bank, OECD paths in the vendor map). Executive intelligence scorecard scores platform trust, learning, and freshness dimensions, marked advisory-only.
      </p>
      <p>
        <strong>Partial:</strong> Weekly Team Status Report and Executive Summary Generation workflows are marketplace starters that agents run against connected context. Our workflow-templates post calls the weekly report the closest starter to a digest, not a scheduled CFO product with computed KPIs.
      </p>
      <p>
        <strong>Not built:</strong> decision-making speed, reporting hours eliminated, or cross-functional KPI rollups as automatic numbers. Intelligence Reports ROI tab leaves hours saved, revenue influenced, and cost savings blank with <code>insufficient_data</code> while still showing operational counts like workflow_executed and connector_action_executed.
      </p>

      <h2>Where to look in the product</h2>
      <ul>
        <li>
          <Link href="/intelligence/reports">Intelligence → Reports</Link> for operational counts and honest gaps on outcome ROI rows.
        </li>
        <li>
          <Link href="/marketplace/analytics/roi">Marketplace → Analytics → ROI</Link> for estimate-only catalog math (read the methodology callout).
        </li>
        <li>
          Installed intelligence packs for PackKpiPanel ingestion counts per pack.
        </li>
        <li>
          <Link href="/metrics">Metrics</Link> for platform operational telemetry (runs, connectors, agents), not department P&amp;L.
        </li>
      </ul>

      <h2>Roadmap direction (not present-tense claims)</h2>
      <p>
        STA-289 ground-truth measurement is the planned path for time-on-task and credible before/after studies. STA-314-style advisory recommendations already explain <em>why</em> a next step is suggested; outcome measurement is a different layer we have not shipped.
      </p>
      <p>
        Until then, the defensible story is operational visibility plus labeled estimates, not fabricated department ratios. Pair this with{" "}
        <Link href="/blog/ai-transparency-and-approval">AI Transparency and the Approval Question</Link> when procurement asks how you trust the automation behind any metric you eventually publish.
      </p>
      <p>
        Browse installable department packs in the <Link href="/marketplace">Marketplace</Link>. Treat catalog hours-saved metadata as a planning hint. Count what Gravitre actually records. Label everything else as estimate or not yet measured.
      </p>
    </>
  ),
}
