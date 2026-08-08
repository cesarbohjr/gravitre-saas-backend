import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"

/**
 * Design-review comp for the four assurance states.
 *
 * Renders the REAL `BusinessOutcomeView` (no reimplementation) four times over
 * the REAL `.ai-chat-canvas` mesh, so a single screenshot answers the two
 * questions a restyle depends on:
 *
 *  1. Is the three-way hierarchy legible — amber (flagged) distinct from red
 *     (failed) and green (verified), without the neutral "unproven" card
 *     reading as an error? Isolated per-state shots cannot show this.
 *  2. Does the flagged card stay opaque on the mesh? `STATE_STYLES.flagged`
 *     omits `bg-card` and supplies only `bg-warning/[0.04]`, which looks like it
 *     contradicts the "solid card surface" requirement the same component
 *     documents for the other three states.
 *
 * Capture-only: the /e2e/shots layout 404s this in production.
 */

const BASE_SECTIONS = {
  evidence: {
    links: [{ label: "View in Salesforce", href: "https://example.salesforce.com/lead/00Q5f", kind: "vendor" }],
  },
  summary: "Enriched 42 inbound leads with firmographic data and routed them to the SDR queue.",
} satisfies BusinessOutcomeDto["sections"]

const OUTCOMES: Array<{ caption: string; outcome: BusinessOutcomeDto }> = [
  {
    caption: "Verified — happened AND independently proven",
    outcome: {
      id: "shot-verified",
      kind: "enrichment",
      status: "completed",
      lifecycleState: "verified",
      title: "42 leads enriched and routed",
      sections: {
        ...BASE_SECTIONS,
        verification: {
          verified: true,
          method: "salesforce_readback",
          detail: "Re-read all 42 records from Salesforce after write; every field matched.",
        },
      },
    },
  },
  {
    caption: "Not verified — happened, but no proof captured",
    outcome: {
      id: "shot-unproven",
      kind: "enrichment",
      status: "completed",
      lifecycleState: "executed",
      title: "18 contacts synced to Mailchimp",
      sections: {
        ...BASE_SECTIONS,
        summary: "Pushed 18 contacts to the Mailchimp audience.",
        verification: {
          verified: false,
          method: "none",
          detail: "Mailchimp does not expose a read-back endpoint for audience writes.",
        },
      },
    },
  },
  {
    caption: "Flagged for review — completed, but the quality check objected",
    outcome: {
      id: "shot-flagged",
      kind: "enrichment",
      status: "flagged_for_review",
      lifecycleState: "executed",
      title: "120 leads enriched — low variance detected",
      sections: {
        ...BASE_SECTIONS,
        summary: "Enriched 120 leads. A batch-quality check objected before the results were handed off.",
        verification: {
          verified: false,
          method: "batch_degeneracy_check",
          reviewState: "flagged_for_review",
          checkFailed: "batch_degeneracy",
          finding: "94 of 120 enriched records share the same industry value — likely a provider fallback, not real data.",
          detail: "The write succeeded; only the confidence in the enriched values is in question.",
          nextActions: [
            "Spot-check 5 flagged records against the provider dashboard",
            "Re-run enrichment with the secondary provider",
            "Approve the batch as-is if the values are correct",
          ],
        },
      },
    },
  },
  {
    caption: "Failed — the action did not happen",
    outcome: {
      id: "shot-failed",
      kind: "enrichment",
      status: "failed",
      lifecycleState: "failed",
      title: "Lead enrichment did not run",
      sections: {
        evidence: BASE_SECTIONS.evidence,
        summary: "The Salesforce write was rejected, so no records were changed.",
        verification: {
          verified: false,
          method: "salesforce_readback",
          detail: "Salesforce returned FIELD_CUSTOM_VALIDATION_EXCEPTION; zero records written.",
        },
      },
    },
  },
]

export default function OutcomeStatesShotPage() {
  return (
    <main className="ai-chat-canvas min-h-screen px-6 py-8" data-chat-bg="marketing">
      <h1 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
        Assurance states · chat density
      </h1>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        {OUTCOMES.map(({ caption, outcome }) => (
          <section key={outcome.id} className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">{caption}</p>
            <BusinessOutcomeView outcome={outcome} density="chat" />
          </section>
        ))}
      </div>
    </main>
  )
}
