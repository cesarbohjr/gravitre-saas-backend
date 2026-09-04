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

  const title = `${doc.frontmatter.title} | Gravitre Docs`
  const description = doc.frontmatter.description
  const ogImage = { url: "/og-docs.png", width: 1200, height: 630, alt: "Gravitre Docs" }

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      images: [ogImage],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/og-docs.png"],
    },
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
    <div className="min-h-screen bg-card">
      <DocsShell sections={sections} headings={headings}>
        <DocPageMotion>
          <DocsBreadcrumb category={frontmatter.category} title={frontmatter.title} />

          <div className="mb-4 flex flex-wrap items-center gap-2.5">
            {frontmatter.category ? (
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                {frontmatter.category}
              </span>
            ) : null}
            {frontmatter.tier && frontmatter.tier !== "all" ? (
              <PlanBadge tier={frontmatter.tier} />
            ) : null}
            {frontmatter.readTime ? (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {frontmatter.readTime} read
              </span>
            ) : null}
          </div>

          <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl text-balance">
            {frontmatter.title}
          </h1>
          {frontmatter.description ? (
            <p className="mt-4 text-lg leading-relaxed text-muted-foreground text-pretty">
              {frontmatter.description}
            </p>
          ) : null}

          <div className="mt-4 flex items-center gap-4 border-b border-border pb-6 text-sm">
            <a
              href={`https://github.com/gravitre/docs/edit/main/content/docs/public/${doc.slug}.mdx`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Edit on GitHub
            </a>
          </div>
        </DocPageMotion>

        <article className="prose prose-zinc mt-8 max-w-none">{content}</article>

        {(frontmatter.prev || frontmatter.next) && (
          <div className="mt-16 border-t border-border pt-8">
            <div className="flex items-center justify-between gap-4">
              {frontmatter.prev ? (
                <Link
                  href={frontmatter.prev.href}
                  className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                >
                  <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                  <span>
                    <span className="block text-xs text-muted-foreground">Previous</span>
                    <span className="font-medium text-foreground">{frontmatter.prev.title}</span>
                  </span>
                </Link>
              ) : (
                <div />
              )}

              {frontmatter.next ? (
                <Link
                  href={frontmatter.next.href}
                  className="group flex items-center gap-2 text-right text-sm text-muted-foreground hover:text-foreground"
                >
                  <span>
                    <span className="block text-xs text-muted-foreground">Next</span>
                    <span className="font-medium text-foreground">{frontmatter.next.title}</span>
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

      <section className="border-t border-border bg-muted/50/50 px-6 py-12">
        <div className="mx-auto max-w-4xl text-center">
          <h3 className="mb-2 text-lg font-medium text-foreground">Need more help?</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Can&apos;t find what you&apos;re looking for? Our team is here to help.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-foreground/90"
            >
              Contact Support
            </Link>
            <a
              href="https://github.com/gravitre"
              className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
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
