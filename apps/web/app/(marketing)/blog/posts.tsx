import type { ReactNode } from "react"
import { GRAVITRE_BLOG_AUTHOR } from "./authors"
import { securityFirstPost } from "./content/security-first"
import { workflowTemplatesPost } from "./content/workflow-templates"
import { aiTransparencyApprovalPost } from "./content/ai-transparency-approval"
import { measuringAiRoiPost } from "./content/measuring-ai-roi"
import { enterpriseAiGovernancePost } from "./content/enterprise-ai-governance"
import { aiAgentBestPracticesPost } from "./content/ai-agent-best-practices"
import { SITE_URL, type BlogFAQ, type BlogPost } from "./types"

export { GRAVITRE_BLOG_AUTHOR } from "./authors"
export { SITE_URL, type BlogAuthor, type BlogFAQ, type BlogPost } from "./types"

const cesar = GRAVITRE_BLOG_AUTHOR

/**
 * Shared link styling for inline citations. Citations matter for GEO: generative
 * engines preferentially surface claims that are backed by named, datable sources.
 */
function Cite({ children }: { children: ReactNode }) {
  return <em className="text-foreground">{children}</em>
}

const aiWontTakeYourJob: BlogPost = {
  slug: "ai-wont-take-your-job-your-resistance-might",
  title: "AI Won't Take Your Job. Your Resistance to It Might.",
  description:
    "40% of workers now fear AI will make their job obsolete, but adoption data shows AI replaces tasks, not people. Here is how to adopt AI as a force multiplier.",
  excerpt:
    "Fear of AI job loss jumped to 40% of workers worldwide, yet companies that adopt AI well reallocate people to higher-value work instead of cutting headcount. The real risk is not AI. It is resisting it.",
  category: "Perspective",
  author: cesar,
  datePublished: "2026-06-22",
  dateModified: "2026-06-22",
  displayDate: "June 22, 2026",
  readTime: "7 min read",
  heroImage: "/images/blog/ai-wont-take-your-job.png",
  heroAlt:
    "A human hand and a glowing AI light form reaching toward each other, symbolizing AI augmenting human work rather than replacing it.",
  keywords: [
    "AI job loss",
    "will AI take my job",
    "AI adoption",
    "future of work",
    "AI augmentation",
    "AI productivity",
    "AI in the workplace",
    "AI training gap",
    "human in the loop",
  ],
  takeaways: [
    "40% of workers worldwide now fear AI will make their job obsolete, up from 28% two years ago (Mercer Global Talent Trends 2026).",
    "88% of organizations already use AI in at least one business function, yet only 17% of those seeing productivity gains reduced headcount.",
    "Generative AI saves workers an average of 2.2 hours per week, and frequent users save over 9 hours.",
    "AI replaces tasks, not people. The most exposed roles involve the least human judgment.",
    "The biggest barrier is not the technology. Over half the global workforce reports no recent AI training.",
  ],
  faqs: [
    {
      question: "Will AI take my job?",
      answer:
        "For most workers, no. Despite 88% of organizations adopting AI, only 17% of those seeing productivity gains reduced headcount, and the majority reallocated people to higher-value work. AI tends to replace specific tasks rather than entire roles, especially work involving human judgment, relationships, and brand experience.",
    },
    {
      question: "Which jobs are most at risk from AI?",
      answer:
        "Roles with the least human judgment are most exposed: data entry, customer service, administrative support, and basic coding. Roles in healthcare, skilled trades, creative leadership, strategy, and relationship-driven work are far more insulated because they depend on trust, lived experience, and human decision-making AI cannot replicate.",
    },
    {
      question: "How much time does AI actually save workers?",
      answer:
        "Federal Reserve research found generative AI saves workers an average of 5.4% of work hours, about 2.2 hours per week, or roughly a full workday reclaimed each month. Frequent users report saving over 9 hours per week.",
    },
    {
      question: "What does it mean to adopt AI properly?",
      answer:
        "Adopting AI properly means using it as a force multiplier for the work only humans can do, like strategy, creativity, relationships, and brand, while keeping a human in the loop to catch errors and hallucinations. It also means investing in training, since over half the workforce reports receiving no recent AI training.",
    },
  ],
  Content: () => (
    <>
      <p>
        For years, I&apos;ve watched marketing technology evolve. Product licensing, commercialization, and distribution
        have matured to the point where consumers know more about what&apos;s available to them than ever before. But
        with every new channel came the same side effect: market saturation.
      </p>
      <p>
        I remember when social media became a serious force in marketing. Businesses were reluctant to buy in. It felt
        unproven, hard to measure, maybe even a fad. Today we&apos;ve gotten much better at tracking social ROI, but the
        market is crowded again. New platforms launch constantly, yet the same three or four continue to dominate
        attention and ad spend.
      </p>
      <p>
        Now we&apos;re standing at the entrance of the AI era, and the conversation feels eerily familiar: adopt, or risk
        becoming obsolete. I think the truth lives somewhere in between, and the data backs that up.
      </p>

      <h2>The fear is real, and it&apos;s growing fast</h2>
      <p>
        This isn&apos;t a fringe anxiety. According to <Cite>Mercer&apos;s Global Talent Trends 2026</Cite> report, a
        survey of 12,000 workers and HR leaders, 40% of workers worldwide now fear AI will make their job obsolete, up
        from 28% just two years ago. That&apos;s a 12-point jump in two years, and the trend line is accelerating, not
        leveling off.
      </p>
      <p>
        In the U.S., a <Cite>Reuters/Ipsos</Cite> poll found 71% of Americans fear AI could permanently wipe out jobs. A
        separate <Cite>ADP Research</Cite> survey of more than 39,000 workers across 36 countries found that in Japan,
        only 5% of workers feel their jobs are secure, the lowest of any market surveyed. The fear isn&apos;t evenly
        spread, either: workers in data entry, customer service, and administrative support report the highest levels of
        concern, while those in healthcare, skilled trades, and creative leadership feel more insulated.
      </p>
      <p>That distinction matters, and it&apos;s really the heart of my argument.</p>

      <h2>Adoption is already the baseline, not the edge case</h2>
      <p>
        Here&apos;s what&apos;s easy to miss in all the anxiety: companies aren&apos;t deliberating over{" "}
        <strong>whether</strong> to adopt AI anymore. They&apos;re past that. <Cite>McKinsey&apos;s 2025 State of AI</Cite>{" "}
        survey found that 88% of organizations now regularly use AI in at least one business function, up from 78% the
        year before. Other industry trackers put broader business adoption above 90%.
      </p>
      <p>
        But adoption hasn&apos;t translated into mass layoffs the way the headlines suggest. One analysis found that
        despite widespread AI use, only 17% of organizations seeing productivity gains actually reduced headcount, and
        the majority reallocated people toward higher-value work instead. That&apos;s the pattern I keep coming back to:
        AI replacing <strong>tasks</strong>, not replacing <strong>people</strong>, in the companies that are doing this
        well.
      </p>
      <p>
        This is the same arc I watched with social media. The tools changed. The skill required to use them well
        didn&apos;t disappear. It shifted.
      </p>

      <h2>What AI actually frees up, when used right</h2>
      <p>
        The premise of AI, done properly, isn&apos;t to make your team smaller. It&apos;s to make your team&apos;s time
        worth more. <Cite>Federal Reserve</Cite> research found generative AI saves workers an average of 5.4% of their
        work hours, roughly 2.2 hours a week, or close to a full workday reclaimed every month. Frequent users save far
        more: nearly 27% of regular AI users report saving over 9 hours a week.
      </p>
      <p>
        That reclaimed time is the entire point. It&apos;s time that can go back into strategy, creative ideation, and the
        human judgment calls that AI still can&apos;t make, instead of being swallowed by administrative drag.
      </p>
      <p>
        The companies pulling ahead seem to understand this distinction instinctively. <Cite>PwC&apos;s 2026 AI
        Performance</Cite> study found that nearly three-quarters of AI&apos;s economic value is being captured by just
        20% of organizations, and those leaders aren&apos;t simply running more AI tools. They&apos;re using AI as a
        platform for growth and reinvention, not just cost-cutting.
      </p>

      <h2>What AI still can&apos;t touch</h2>
      <p>
        I don&apos;t believe AI will ever replace human beings, and I don&apos;t think that&apos;s wishful thinking.
        It&apos;s structural. Brand experience is emotion. Buyer behavior is shaped by lived experience, trust, and the
        specific culture a company has built into its products and its people over years. That&apos;s not a dataset.
        It&apos;s not a prompt. It&apos;s the accumulated, often irrational, deeply human texture of how people decide
        what to believe in and buy.
      </p>
      <p>
        AI can draft the brief. It can&apos;t <strong>be</strong> the relationship. It can summarize the research. It
        can&apos;t sit across the table and read the hesitation in a client&apos;s voice. The most exposed roles right
        now, like data entry, basic coding, and administrative support, are exposed precisely because they involve less
        of that human judgment, not because AI has become &quot;smarter&quot; than people in any meaningful sense.
      </p>
      <p>
        This is also where AI hallucination still matters. Models get things confidently wrong. Human talent has to be in
        the loop to catch what AI can&apos;t catch about itself.
      </p>

      <h2>So what does doing it properly actually look like?</h2>
      <p>
        It looks like giving your team the tools to move past administrative and technical friction faster than they
        could alone, then trusting them to spend that time on the work they were actually hired to do. Product teams that
        integrate AI well aren&apos;t working less; they&apos;re blowing past sprint timelines with the time AI buys them,
        while still keeping a human in the loop to catch what the model gets wrong.
      </p>
      <p>
        It also means being honest about the gap that&apos;s currently undermining a lot of AI investment: more than half
        the global workforce reports receiving no recent AI training, according to{" "}
        <Cite>ManpowerGroup&apos;s 2026 Global Talent Barometer</Cite>. You can&apos;t expect a team to feel empowered by a
        tool nobody taught them to use. That training gap, not the technology itself, is where I think most of the real
        anxiety is actually rooted.
      </p>

      <h2>Adopt, but adopt like you mean it</h2>
      <p>
        I keep landing back on the same comparison: social media didn&apos;t replace marketers, it changed what marketing
        competence looked like. AI is doing the same thing, faster. The companies and people who treat it as a force
        multiplier for the work only humans can do, like strategy, creativity, relationship, and brand, are going to
        outpace the ones who either ignore it or use it purely to cut headcount.
      </p>
      <p>
        It sounds easier than it is. But when AI is used properly, it doesn&apos;t make your team smaller. It makes the
        work your team was always meant to do finally possible to get to. That&apos;s exactly the problem we built{" "}
        <a href="/get-started">Gravitre</a> to solve, giving teams AI agents that absorb the administrative drag so the
        humans can get back to the work only they can do. If that&apos;s the kind of adoption you&apos;re after, you can{" "}
        <a href="/get-started">try Gravitre free</a> and see what your team does with the time back.
      </p>
    </>
  ),
}

/** Placeholder entries removed from index — no published article yet. */
export const BLOG_LISTING_EXCLUDED_SLUGS = new Set([
  "case-study-acme-corp",
  "series-b-announcement",
])

export const blogPosts: BlogPost[] = [
  aiWontTakeYourJob,
  aiTransparencyApprovalPost,
  measuringAiRoiPost,
  securityFirstPost,
  workflowTemplatesPost,
  enterpriseAiGovernancePost,
  aiAgentBestPracticesPost,
]

export function getFeaturedBlogPost(): BlogPost {
  return [...blogPosts].sort((a, b) => b.datePublished.localeCompare(a.datePublished))[0]
}

export function getBlogListingPosts(): BlogPost[] {
  const featuredSlug = getFeaturedBlogPost().slug
  return blogPosts
    .filter(
      (post) => post.slug !== featuredSlug && !BLOG_LISTING_EXCLUDED_SLUGS.has(post.slug),
    )
    .sort((a, b) => b.datePublished.localeCompare(a.datePublished))
}

export function getBlogCategories(): string[] {
  const cats = new Set(blogPosts.map((p) => p.category))
  return ["All", ...Array.from(cats).sort()]
}

export function getBlogPost(slug: string): BlogPost | undefined {
  return blogPosts.find((post) => post.slug === slug)
}

export function getAllBlogSlugs(): string[] {
  return blogPosts.map((post) => post.slug)
}
