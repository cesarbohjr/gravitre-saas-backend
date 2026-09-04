import type { BlogPost } from "../types"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

export const securityFirstPost: BlogPost = {
  slug: "security-first-approach",
  title: "Our Security-First Approach to AI Automation",
  description:
    "How we build AI automation for least privilege, verified execution, and auditability — including a governance gap we found in our own platform and fixed.",
  excerpt:
    "AI automation only scales when security is built in, not bolted on. Here's how we design for least privilege, verified execution, and auditability — and what we do when we find out we got it wrong.",
  category: "Security",
  author: GRAVITRE_BLOG_AUTHOR,
  datePublished: "2026-03-28",
  dateModified: "2026-07-13",
  displayDate: "March 28, 2026",
  readTime: "6 min read",
  heroImage: "/images/blog/security-first-hero.jpg",
  heroGradient: "from-slate-100 via-primary/5 to-muted",
  heroAlt:
    "Glossy translucent glass blocks refracting glowing streams of AI action words, evoking layered, controlled AI automation.",
  keywords: [
    "AI automation security",
    "least privilege",
    "human in the loop approvals",
    "audit trails",
    "AI governance",
    "OAuth connector security",
  ],
  takeaways: [
    "We treat connector credentials and model outputs as sensitive data — encrypted in transit and at rest, scoped by environment.",
    "Every write action requires explicit approval before it executes. Not as a feature toggle — as the only path an action can take.",
    "We derive write authority from a schema catalog, not from pattern-matching action names. That distinction matters more than it sounds.",
    "When we find a gap, we say so. This post includes one we found and fixed, because a security post that only lists what already works isn't the one you need.",
    "Governance decisions about sensitive data are never authorized by an engineering test passing. They get a named human owner.",
  ],
  faqs: [
    {
      question: "Does AI automation mean giving models unlimited API access?",
      answer:
        "No. Production AI should run with least privilege: scoped connectors, environment isolation, and approval gates on every high-impact write, derived from a schema catalog rather than a naming convention that can be guessed around.",
    },
    {
      question: "What should we audit for AI workflows?",
      answer:
        "Authentication events, connector health changes, workflow publishes, approval decisions, and run outcomes — for every path an action can take through the system, not just the one that's easiest to test.",
    },
    {
      question: "How do we reduce OAuth and scope drift risk?",
      answer:
        "Monitor Configured → Authenticated → Healthy → Executable status continuously. Re-authenticate before scopes expire — don't discover the failure mid-workflow.",
    },
    {
      question: "What happens when you find a gap in your own governance?",
      answer:
        "We fix it, we add a permanent test so the same class of gap can't return quietly, and we tell you about it if it's material. A vendor that only talks about the controls that already work isn't giving you the full picture you need for your own risk assessment.",
    },
  ],
  Content: () => (
    <>
      <p>
        Security teams are right to be skeptical of AI automation. When a model can call CRMs, ticketing systems, and
        finance tools, the blast radius of a misconfigured integration isn&apos;t a bad chat reply — it&apos;s a
        production write in the wrong place, to the wrong record, with nobody watching.
      </p>
      <p>
        At Gravitre, we treat security as a product requirement, not a sales slide. That means encryption by default,
        role-based access, environment isolation, and audit trails that survive an actual incident review — which we
        know because we&apos;ve run that review on ourselves.
      </p>

      <h2>Least privilege for agents and connectors</h2>
      <p>
        Every connector uses OAuth or scoped API keys stored server-side — never embedded in prompts. Agents receive
        only the actions your policy allows for the active environment. We show{" "}
        <strong>Configured → Authenticated → Healthy → Executable</strong> readiness so you see a missing scope before a
        run starts, not after a record was partially updated.
      </p>
      <p>
        Here&apos;s the part we don&apos;t put in most product copy: we found out the hard way that &ldquo;gated&rdquo;
        isn&apos;t a property you get once and keep forever. Early in hardening our platform-level actions — workflow
        creation, agent execution, the internal operations chat can trigger on your behalf — we discovered three of them
        were explicitly marked as exempt from the approval gate that every connector write already went through. Not a
        bug in the traditional sense. A flag, set on purpose at some earlier point, that no longer matched what the
        system needed to guarantee.
      </p>
      <p>
        We found it by auditing our own internal action surface with the same scrutiny we&apos;d apply to a
        customer&apos;s connector, closed it the same day, and added a permanent automated test that fails the build if
        any write-capable action is ever registered without going through the approval path again. We&apos;re telling
        you this not because it makes us look good — it&apos;s a gap we should have caught sooner — but because
        &ldquo;we audit ourselves this hard&rdquo; is a claim that only means something if we show our work.
      </p>

      <h2>Human approval on high-impact actions</h2>
      <p>
        Autonomy without accountability is how teams lose trust in AI. Every write — a CRM update, a workflow execution,
        a list created in a connected tool — shows you exactly what&apos;s about to happen before it happens: the
        action, the target, and anything Gravitre inferred rather than was explicitly told. If we filled in a default
        because you didn&apos;t specify one, we say so in the approval card. We don&apos;t present a guess as a fact.
      </p>
      <p>
        We derive <strong>which</strong> actions require this gate from a single schema catalog — not from checking
        whether an action&apos;s name contains a word like &ldquo;create&rdquo; or &ldquo;delete.&rdquo; That
        distinction sounds pedantic until you&apos;ve watched a pattern-based check silently miss an action because it
        was named a way nobody anticipated. We rebuilt this to read authority from the same structured catalog every
        action is already registered in, specifically because pattern-matching is exactly the kind of check that looks
        complete and isn&apos;t.
      </p>

      <h2>Verified output, not just verified input</h2>
      <p>
        Most platforms stop at &ldquo;did the write succeed.&rdquo; We ask a second question:{" "}
        <strong>can the user actually verify what happened?</strong> A success response that says nothing useful is a
        trust gap wearing a green checkmark. Every governed write is expected to return either a real, human-readable
        summary or a working link back to the actual record it created — not a link to our own settings page standing in
        for one.
      </p>
      <p>
        We built a standing test for this: a write can&apos;t be marked complete unless it satisfies that bar. Where a
        vendor genuinely doesn&apos;t expose a way to verify the result, we say so plainly instead of guessing at a link
        that might be wrong.
      </p>

      <h2>Auditability that auditors actually use</h2>
      <p>
        History captures administrative and security-relevant events — who triggered it, what executed, what was
        skipped, and why. Enterprise customers can export to SIEM. Run detail shows step-level status with connector
        context attached, all the way down to the specific error code, not a model&apos;s paraphrase of one.
      </p>
      <p>
        If you can&apos;t reconstruct a workflow run from logs alone, you don&apos;t have governance — you have hope.
      </p>

      <h2>What we will not claim</h2>
      <p>
        No platform eliminates risk. Models infer things that turn out wrong. Integrations break. Data governance
        questions — like whether contact information should ever be sent to a third-party model for processing —
        don&apos;t get resolved by an engineering test passing, and we don&apos;t treat them as if they do. Those
        decisions have a named owner, separate from the engineering team that ships the code, and a schema check
        clearing is never mistaken for that owner&apos;s sign-off.
      </p>
      <p>
        Our job is to make failures visible early, contain blast radius, hold write actions to the same evidentiary bar
        whether they&apos;re brand new or eighteen months old, and leave a paper trail that would actually hold up if
        someone had to reconstruct what happened. That&apos;s the bar for AI automation in regulated and
        revenue-critical teams — and it&apos;s the bar we hold ourselves to, including when we&apos;re the ones grading
        our own work.
      </p>
      <p>
        If your security review asks how AI touches production data, start with{" "}
        <Link href="/docs/concepts/security">our security overview</Link> or{" "}
        <Link href="/features">see how approvals and connector checks work in product</Link>.
      </p>
    </>
  ),
}
