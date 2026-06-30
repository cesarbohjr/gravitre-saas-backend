import Link from "next/link"
import { compileMDX } from "next-mdx-remote/rsc"
import { notFound } from "next/navigation"
import remarkGfm from "remark-gfm"
import rehypeSlug from "rehype-slug"
import { ArrowLeft, ArrowRight, Clock, ExternalLink } from "lucide-react"

import { mdxComponents } from "@/lib/docs/mdx-components"
import {
  getAllPublicDocSlugs,
  getPublicDocBySlug,
  getDocsNavSections,
} from "@/lib/docs/load-docs"
import { extractHeadings } from "@/lib/docs/toc"
import { DocsShell } from "@/components/docs/docs-shell"
import { DocsBreadcrumb } from "@/components/docs/docs-breadcrumb"
import { PlanBadge } from "@/components/docs/plan-badge"

import { DocPageMotion } from "./doc-page-motion"

export async function generateStaticParams() {
  return getAllPublicDocSlugs().map((slug) => ({
    slug: slug.split("/"),
  }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug?: string[] }>
}) {
  const { slug = [] } = await params
  const doc = getPublicDocBySlug(slug.join("/"))
  if (!doc) return { title: "Documentation | Gravitre" }

  return {
    title: `${doc.frontmatter.title} | Gravitre Docs`,
    description: doc.frontmatter.description,
  }
}

export default async function DocsSlugPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>
}) {
  const { slug = [] } = await params
  const slugPath = slug.join("/")
  const doc = getPublicDocBySlug(slugPath)
  if (!doc) notFound()

  const { content } = await compileMDX({
    source: doc.content,
    components: mdxComponents,
    options: {
      parseFrontmatter: false,
      mdxOptions: {
        remarkPlugins: [remarkGfm],
        rehypePlugins: [rehypeSlug],
      },
    },
  })

  const { frontmatter } = doc
  const headings = extractHeadings(doc.content)
  const sections = getDocsNavSections()

  return (
    <div className="min-h-screen bg-white">
      <DocsShell sections={sections} headings={headings}>
        <DocPageMotion>
          <DocsBreadcrumb category={frontmatter.category} title={frontmatter.title} />

          <div className="mb-4 flex flex-wrap items-center gap-2.5">
            {frontmatter.category ? (
              <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
                {frontmatter.category}
              </span>
            ) : null}
            {frontmatter.tier && frontmatter.tier !== "all" ? (
              <PlanBadge tier={frontmatter.tier} />
            ) : null}
            {frontmatter.readTime ? (
              <span className="flex items-center gap-1 text-xs text-zinc-500">
                <Clock className="h-3 w-3" />
                {frontmatter.readTime} read
              </span>
            ) : null}
          </div>

          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl text-balance">
            {frontmatter.title}
          </h1>
          {frontmatter.description ? (
            <p className="mt-4 text-lg leading-relaxed text-zinc-600 text-pretty">
              {frontmatter.description}
            </p>
          ) : null}

          <div className="mt-4 flex items-center gap-4 border-b border-zinc-200 pb-6 text-sm">
            <a
              href={`https://github.com/gravitre/docs/edit/main/content/docs/public/${doc.slug}.mdx`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-zinc-500 transition-colors hover:text-zinc-900"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Edit on GitHub
            </a>
          </div>
        </DocPageMotion>

        <article className="prose prose-zinc mt-8 max-w-none">{content}</article>

        {(frontmatter.prev || frontmatter.next) && (
          <div className="mt-16 border-t border-zinc-200 pt-8">
            <div className="flex items-center justify-between gap-4">
              {frontmatter.prev ? (
                <Link
                  href={frontmatter.prev.href}
                  className="group flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900"
                >
                  <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                  <span>
                    <span className="block text-xs text-zinc-500">Previous</span>
                    <span className="font-medium text-zinc-900">{frontmatter.prev.title}</span>
                  </span>
                </Link>
              ) : (
                <div />
              )}

              {frontmatter.next ? (
                <Link
                  href={frontmatter.next.href}
                  className="group flex items-center gap-2 text-right text-sm text-zinc-500 hover:text-zinc-900"
                >
                  <span>
                    <span className="block text-xs text-zinc-500">Next</span>
                    <span className="font-medium text-zinc-900">{frontmatter.next.title}</span>
                  </span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
              ) : (
                <div />
              )}
            </div>
          </div>
        )}
      </DocsShell>

      <section className="border-t border-zinc-200 bg-zinc-50/50 px-6 py-12">
        <div className="mx-auto max-w-4xl text-center">
          <h3 className="mb-2 text-lg font-medium text-zinc-900">Need more help?</h3>
          <p className="mb-4 text-sm text-zinc-500">
            Can&apos;t find what you&apos;re looking for? Our team is here to help.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
            >
              Contact Support
            </Link>
            <a
              href="https://github.com/gravitre"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-200 px-5 py-2.5 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-50"
            >
              <ExternalLink className="h-4 w-4" />
              GitHub
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}
