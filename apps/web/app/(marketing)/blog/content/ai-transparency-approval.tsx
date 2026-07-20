import type { BlogPost } from "../types"
import { createBlogDates } from "../blog-dates"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

export const aiTransparencyApprovalPost: BlogPost = {
  slug: "ai-transparency-and-approval",
  title: "AI Transparency and the Approval Question",
  description:
    "See exactly how Gravitre approves AI actions, verifies results, and logs every write, so you always know who approved what and why.",
  excerpt:
    "Transparency is not a values slide. It is whether you can always answer three questions: who approved this, what did the AI assume, and where is the record?",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  ...createBlogDates("2026-07-17", "2026-07-18"),
  readTime: "6 min read",
  heroImage: "/images/blog/ai-transparency-approval-hero.jpg",
  heroGradient: "from-emerald-50 via-white to-slate-100",
  heroAlt:
    "Diagram showing an AI action moving through an approval step, a verification check, and an audit log entry",
  keywords: [
    "AI transparency",
    "human in the loop approval",
    "AI audit trail",
    "explainable AI automation",
    "verified AI actions",
    "AI governance",
  ],
  takeaways: [
    "Any action that changes something in your systems goes through the same approval standard, whether it starts in chat, a guided task, or an automated workflow.",
    "If someone without approval rights asks the AI to do something, it queues the request and tells them plainly that it is waiting on approval.",
    "When a write succeeds, you get real proof: a link to the record it created or changed, or a summary of what happened. If neither is available, we tell you it failed rather than showing a false success.",
    "When the AI has to guess at a detail instead of reading it directly from what you said, it tells you that too.",
    "Suggestions from Gravitre always come with a plain-language reason and the evidence behind it. Nothing executes on its own.",
    "Every approval and action is logged and reviewable, so you are never left guessing after the fact.",
  ],
  faqs: [
    {
      question: "Does every AI action that changes something need approval?",
      answer:
        "Any action classified as a write goes through approval logic based on your company's policy and your role. Depending on your permissions, you may approve it yourself in the moment, or it queues for someone who can. Actions that just read information do not require this step.",
    },
    {
      question: "Can automated workflows skip the approval rules that apply to chat?",
      answer:
        "No. Every path, whether chat, guided steps, or automated workflows, is held to the same approval standard. If a workflow step requires approval, it stops and waits, with nothing executed until a human signs off.",
    },
    {
      question: "Can I see why Gravitre suggested something?",
      answer:
        "Yes. Every suggestion comes with a plain-language reason and supporting evidence. They are advisory only. Nothing executes without a person choosing to act on it.",
    },
    {
      question: "What happens if an AI action does not return clear proof it worked?",
      answer:
        "If Gravitre cannot provide a link to the result or a clear summary, the action is marked as failed rather than shown as a false success. Some read-only actions may not include a direct link by design, since there is nothing new created to link to.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>
          Transparency is not a values slide. It is whether you can always answer three questions: who approved
          this, what did the AI assume, and where is the record?
        </strong>
      </p>

      <aside
        aria-label="Quick answer"
        className="not-prose mt-8 rounded-2xl border border-zinc-200 bg-zinc-50 p-6"
      >
        <p className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Quick answer</p>
        <p className="mt-3 text-base leading-relaxed text-zinc-700">
          Gravitre requires human approval before any AI action that changes your data, shows verifiable proof when
          that action succeeds, tells you when it had to guess at a detail, and logs every approval and result so you
          can review it later. This applies the same way whether the request comes from chat, a guided task, or an
          automated workflow.
        </p>
      </aside>

      <h2>Trust is not a feeling. It is something you can check.</h2>
      <p>
        A lot of AI products talk about &ldquo;trust&rdquo; and &ldquo;transparency&rdquo; as a tone: reassuring
        language, a friendly explanation, a badge on the pricing page. We think that is the wrong test. The real
        question is much simpler. <strong>When this thing takes an action on your behalf, can you actually verify what
        happened?</strong>
      </p>
      <p>
        That is the standard we hold Gravitre to. Not a promise. A mechanism you can go check yourself.
      </p>

      <h2>Does every AI action need approval?</h2>
      <p>
        You might ask Gravitre to do something directly in a chat message. You might be stepping through a guided task.
        Or you might have a full automated workflow running in the background. However the request comes in, it hits
        the exact same approval standard. There is no side door where a workflow gets to skip the rules a chat message
        would follow.
      </p>
      <p>
        That is the bar we hold ourselves to. It should not matter which path a request comes through. If it needs
        approval, it waits for approval, every time.
      </p>

      <h2>Who approves AI actions, and what everyone sees</h2>
      <p>Approval is not a setting someone can quietly switch off for convenience. It is built into how every write action works:</p>
      <ul>
        <li>
          If you have approval rights and your company&apos;s policy allows it, you will see a confirmation step right
          in the moment, and can approve it yourself.
        </li>
        <li>
          If you do not have approval rights, your request does not just vanish or run anyway. You will see a clear
          message that it has been sent for approval, and it lands in a queue an approver can review at{" "}
          <Link href="/approvals">Approvals</Link>.
        </li>
        <li>
          Your company controls all of this from one place: who can approve what, and for which kinds of actions, in{" "}
          <Link href="/settings/approvals">Settings → Approvals</Link>.
        </li>
      </ul>
      <p>
        For multi-step automated runs, each step is labeled up front as something that just reads information, or
        something that changes it and needs approval. That way you know exactly what is coming before it happens, not
        after something has already changed.
      </p>

      <h2>Real proof it worked, not just a checkmark</h2>
      <p>
        A green checkmark that does not lead anywhere is not proof of anything. When a write action succeeds, Gravitre
        shows you one of a few honest outcomes:
      </p>
      <ul>
        <li>
          <strong>Verified</strong>: a direct link to the record that was created or updated, so you can go look at it
          yourself.
        </li>
        <li>
          <strong>Completed, with a summary</strong>: a direct link is not available, but you still get a clear
          description of what happened.
        </li>
        <li>
          <strong>Failed</strong>: neither a link nor a clear result is available. We would rather tell you it failed
          than show you a success we cannot back up.
        </li>
      </ul>

      <h2>When Gravitre guesses, it tells you</h2>
      <p>
        Sometimes completing a task means filling in a small detail you did not explicitly provide, like a default name
        for something you asked to create. When that happens, Gravitre shows you an <strong>Assumptions</strong> note,
        separate from the summary of what it did, so you always know what came directly from you and what the AI filled
        in on its own.
      </p>
      <p>
        This is still expanding to cover more situations over time, and we would rather be upfront that it is not
        everywhere yet than pretend every judgment call the AI makes is spelled out today.
      </p>

      <h2>Suggestions you can trust, not a black box</h2>
      <p>
        Gravitre also surfaces proactive suggestions on <Link href="/intelligence">Intelligence</Link>, like recommending
        you connect a tool you have not set up yet, or pointing out a useful next step. Every one of these comes with a
        plain-language reason and the evidence behind it, so you are never just told to trust it.
      </p>
      <p>
        And importantly, these suggestions are just that: suggestions. There is no button that lets a recommendation
        execute itself. A human decides.
      </p>

      <h2>Real citations, or an honest &ldquo;here is where to look&rdquo;</h2>
      <p>
        When Gravitre answers a question using your connected knowledge sources, you will see real, numbered citations
        you can click through to the source. If a search does not turn up a good match, we do not invent a citation to
        look complete. You will see a clear link to check your sources directly at{" "}
        <Link href="/sources">Sources</Link>.
      </p>

      <h2>Is there an audit trail for every AI action?</h2>
      <p>
        Every approval and every action is logged, and you can review, filter, and export that history any time from
        your <Link href="/audit">audit page</Link>. If you are investigating something after the fact, whether that is
        a change you did not expect or confirming a policy was followed, the record is there.
      </p>
      <p>
        We will be upfront that this is an area we are continuing to strengthen. Some advanced audit features are tied
        to specific plans today, and we are working toward an even more unified view. But the core principle holds:
        nothing important happens without a trace you can go find.
      </p>

      <h2>What is next</h2>
      <p>
        We are expanding assumption labeling to cover more situations, broadening citation coverage, and tightening
        the audit experience even further. As always, we will tell you plainly what is shipped versus what is still on
        the way. That is the same discipline that shapes every claim on this page.
      </p>
      <p>
        If you are also curious about how we think about measuring the actual impact of automation, our post on{" "}
        <Link href="/blog/measuring-what-ai-changes">measuring what AI actually changes</Link> is a natural next read.
      </p>
    </>
  ),
}
