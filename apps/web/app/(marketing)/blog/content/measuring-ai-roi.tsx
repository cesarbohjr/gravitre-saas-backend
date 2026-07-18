import type { BlogPost } from "../types"
import { createBlogDates } from "../blog-dates"
import { GRAVITRE_BLOG_AUTHOR } from "../authors"
import Link from "next/link"

export const measuringAiRoiPost: BlogPost = {
  slug: "measuring-what-ai-changes",
  title: "Measuring What AI Actually Changes",
  description:
    "See exactly what Gravitre measures today, what's an estimate, and what's coming next, so you always know what a number actually means.",
  excerpt:
    "Every AI vendor shows you a slick ROI chart. Here is what we show you instead: the real thing.",
  category: "Product",
  author: GRAVITRE_BLOG_AUTHOR,
  ...createBlogDates("2026-07-17", "2026-07-18"),
  readTime: "6 min read",
  heroImage: "",
  heroGradient: "from-slate-50 via-emerald-50/40 to-zinc-100",
  heroAlt:
    "Dashboard showing real automation activity alongside a clearly labeled estimate figure",
  keywords: [
    "AI ROI measurement",
    "AI automation metrics",
    "AI governance metrics",
    "department AI ROI",
    "verified AI outcomes",
    "AI transparency",
  ],
  takeaways: [
    "Every automation you run gives you a live, honest picture of what is actually happening, not a story dressed up to look like data.",
    "Where estimates are used, we show you exactly where that number came from and what it is based on, so you can weigh it appropriately.",
    "We are building toward fully verified, real-dollar ROI reporting next, and it will show up alongside the activity data you already rely on.",
    "The point is not to hide what we have not built yet. It is to make sure the number in front of you always means what it says it means.",
  ],
  faqs: [
    {
      question: "What does Gravitre actually show me about my automations?",
      answer:
        "Real, live activity: what ran, what data moved, and what got done. It is the clearest way to know your AI is actually doing the work, without waiting on a quarterly summary.",
    },
    {
      question: 'What do the "hours saved" numbers on pre-built workflows mean?',
      answer:
        "They are estimates from the people who built that automation, clearly labeled so you always know what kind of number you are looking at: useful for planning, not the same as a measured result.",
    },
    {
      question: "Can I see real sales or support data reflected in Gravitre?",
      answer:
        "Yes. Data from your connected tools feeds directly into the relevant workflows, so your team is always working from what is actually there, not a summary layered on top of it.",
    },
    {
      question: "Is fully verified, real-dollar ROI reporting coming?",
      answer:
        "Yes. It is our next major milestone on this front, and it will follow the same principle as everything else here: real data, clearly labeled, nothing invented.",
    },
  ],
  Content: () => (
    <>
      <p>
        <strong>Every AI vendor shows you a slick ROI chart. Here is what we show you instead: the real thing.</strong>
      </p>

      <aside
        aria-label="Quick answer"
        className="not-prose mt-8 rounded-2xl border border-zinc-200 bg-zinc-50 p-6"
      >
        <p className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Quick answer</p>
        <p className="mt-3 text-base leading-relaxed text-zinc-700">
          Gravitre shows you real, live activity from every automation you run, clearly labels any estimated figures with
          their source, and openly says &ldquo;not enough data yet&rdquo; rather than inventing an outcome it has not
          measured. Fully verified, real-dollar ROI reporting is on the roadmap next.
        </p>
      </aside>

      <h2>Does Gravitre publish before and after ROI numbers?</h2>
      <p>
        You have seen the slide. Some case study with a big arrow going from &ldquo;40 hours&rdquo; to &ldquo;10 hours
        a week.&rdquo; It looks great in a demo. The problem is, you have no way to check it, and honestly, neither do
        we when another company shows it to us. A number with no way to verify it is not really a number. It is a
        marketing decision.
      </p>
      <p>
        Most teams evaluating AI tools have been burned by this before. A vendor promises a dashboard full of dollar
        figures, and six months in, nobody can explain where those figures actually came from, or trust them enough to
        put them in front of a CFO.
      </p>
      <p>
        We think the more useful question is not &ldquo;what is the biggest number you can show me.&rdquo; It is
        &ldquo;what can I actually rely on when I make a decision.&rdquo; That is the standard we built Gravitre&apos;s
        reporting around.
      </p>

      <h2>What kinds of numbers does Gravitre actually show?</h2>
      <p>
        Not all metrics are created equal, and pretending otherwise is where most AI ROI claims go wrong. We think about
        the numbers in three tiers:
      </p>
      <p>
        <strong>What actually happened.</strong> Real activity from your own automations: records processed, tasks
        completed, connections used. This is ground truth. It is not a projection or a promise; it is a log of work that
        was actually done.
      </p>
      <p>
        <strong>What is estimated.</strong> Some figures, like an &ldquo;hours saved&rdquo; number attached to a
        pre-built workflow, come from the person who built that automation and knows it best. We treat that the way you
        would treat an experienced contractor&apos;s time estimate on a renovation: useful, informed, worth planning
        around, but not the same thing as a receipt.
      </p>
      <p>
        <strong>What we have not verified yet.</strong> For certain outcomes, we simply do not have enough real,
        measured data to responsibly put a number on it. Rather than fill that gap with something that sounds
        impressive, we leave it open, and we are actively working to close it the right way.
      </p>
      <p>
        Knowing which tier a number belongs to changes how you use it. A real activity count tells you the system is
        working. An estimate helps you plan. And an honest gap tells you where to be appropriately cautious. If you have
        ever had to defend a vendor&apos;s numbers to your own leadership, you know that is worth more than it sounds.
      </p>

      <h2>What this looks like day to day</h2>
      <p>
        Say your team turns on an automation that handles first-pass triage for inbound support tickets. From day one,
        you can see exactly how many tickets it touched, how it categorized them, and where it handed off to a human.
        That is not a projection. It is what happened, visible as it happens.
      </p>
      <p>
        If that same automation came from our library with an estimated time-savings figure attached, you will see that
        clearly marked as an estimate from its creator, not folded into your own operational data as if we measured it
        ourselves. The two numbers live side by side, but they never get confused with each other.
      </p>
      <p>
        This same pattern shows up across the teams using Gravitre. Marketing teams get live signal on what is
        happening with their connected tools alongside estimated savings on pre-built campaign workflows. Sales teams get
        clear visibility into what their connected tools are actually returning, without any guesswork about plan limits
        or data gaps. IT and security teams get a steady, current feed of real threat intelligence. Support and success
        teams see real ticket and account data informing their reviews, not a black-box score. And leadership gets a
        current external view of the market alongside a clear read on what their own teams are actually producing.
      </p>
      <p>
        In every case, the goal is the same: you should never have to wonder whether a number in front of you is real,
        estimated, or a guess wearing real data&apos;s clothes.
      </p>

      <h2>Why this matters more as AI gets more capable</h2>
      <p>
        As AI takes on more of the actual work, not just suggestions but real actions across your systems, the ability
        to see clearly what happened becomes more important, not less. It is one thing to trust a recommendation. It is
        another to hand off real tasks and need to know, with certainty, what was actually done and what it produced.
      </p>
      <p>
        That is really what this is about. Not a reporting feature bolted onto the side of the product, but the same
        principle that shapes how Gravitre approaches automation generally: visibility first, so trust can follow.
      </p>

      <h2>What is next</h2>
      <p>
        We are building toward fully verified, real-dollar ROI: the kind backed by actual measured outcomes rather than
        estimates. As that rolls out, it will sit right alongside the activity data you already see today, following
        the same rule: nothing gets shown until it means what it says.
      </p>
      <p>
        If you are thinking through how to build trust in automation before handing it real work, our post on{" "}
        <Link href="/blog/ai-transparency-and-approval">AI transparency and approval</Link> is a natural next read.
      </p>
    </>
  ),
}
