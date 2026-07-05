import Link from "next/link"
import { compileMDX } from "next-mdx-remote/rsc"
import { notFound } from "next/navigation"
import remarkGfm from "remark-gfm"
import { ArrowLeft, ExternalLink } from "lucide-react"

import { mdxComponents } from "@/lib/docs/mdx-components"
import { getPublicDocBySlug } from "@/lib/docs/load-docs"
import { parseFaq } from "@/lib/docs/parse-faq"
import {
  FaqExperience,
  type FaqClientSection,
} from "@/components/docs/faq-experience"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata = {
  title: "FAQ | Gravitre Docs",
  description: MARKETING_COPY.docs.faqIntro,
}

async function renderMarkdown(source: string) {
  if (!source.trim()) return null
  const { content } = await compileMDX({
    source,
    components: mdxComponents,
    options: {
      parseFrontmatter: false,
      mdxOptions: { remarkPlugins: [remarkGfm] },
    },
  })
  return content
}

export default async function FaqPage() {
  const doc = getPublicDocBySlug("faq")
  if (!doc) notFound()

  const parsed = parseFaq(doc.content)

  const sections: FaqClientSection[] = await Promise.all(
    parsed.map(async (section) => ({
      id: section.id,
      title: section.title,
      intro: await renderMarkdown(section.intro),
      questions: await Promise.all(
        section.questions.map(async (q) => ({
          id: q.id,
          question: q.question,
          searchText: q.searchText,
          answer: await renderMarkdown(q.answer),
        })),
      ),
    })),
  )

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-5xl px-6 py-16">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-1.5 text-sm text-zinc-500 transition-colors hover:text-zinc-900"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to docs
        </Link>

        <header className="mb-12">
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
            FAQ
          </span>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl text-balance">
            Frequently asked questions
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-zinc-600 text-pretty">
            {MARKETING_COPY.docs.faqIntro}
          </p>
        </header>

        <FaqExperience sections={sections} />

        <div className="mt-16 rounded-2xl border border-zinc-200 bg-zinc-50/60 px-6 py-10 text-center">
          <h2 className="text-lg font-medium text-zinc-900">Still have questions?</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-zinc-500">
            Can&apos;t find the answer you&apos;re looking for? Reach out and our team will help.
          </p>
          <div className="mt-5 flex items-center justify-center gap-3">
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
            >
              Contact support
            </Link>
            <a
              href="mailto:support@gravitre.app"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-200 px-5 py-2.5 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-50"
            >
              <ExternalLink className="h-4 w-4" />
              support@gravitre.app
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
