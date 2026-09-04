import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, ArrowRight, Clock, Calendar } from "lucide-react"
import { SITE_URL, getAllBlogSlugs, getBlogPost, type BlogPost } from "../posts"

export const dynamicParams = false

export function generateStaticParams() {
  return getAllBlogSlugs().map((slug) => ({ slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  const post = getBlogPost(slug)
  if (!post) return { title: "Post not found" }

  const url = `${SITE_URL}/blog/${post.slug}`
  const ogImage = post.heroImage
    ? `${SITE_URL}${post.heroImage}`
    : `${SITE_URL}/images/gravitre-logo-black.png`
  return {
    metadataBase: new URL(SITE_URL),
    title: `${post.title} | Gravitre Blog`,
    description: post.description,
    keywords: post.keywords,
    authors: [{ name: post.author.name, url: `${SITE_URL}/about` }],
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      url,
      title: post.title,
      description: post.description,
      siteName: "Gravitre",
      publishedTime: post.datePublished,
      modifiedTime: post.dateModified,
      authors: [post.author.name],
      tags: post.keywords,
      images: [{ url: ogImage, width: 1200, height: 630, alt: post.heroAlt }],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.description,
      images: [ogImage],
    },
  }
}

  /** Brand monogram avatar. Avoids fabricating a likeness while keeping the byline polished. */
function AuthorAvatar({ name, className = "" }: { name: string; className?: string }) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
  return (
    <span
      aria-hidden
      className={`grid place-items-center rounded-full bg-primary font-semibold text-white ${className}`}
    >
      {initials}
    </span>
  )
}

/** All structured data for rich results, AEO answer extraction, and GEO source trust. */
function ArticleJsonLd({ post }: { post: BlogPost }) {
  const url = `${SITE_URL}/blog/${post.slug}`
  const author = {
    "@type": "Person",
    name: post.author.name,
    jobTitle: post.author.role,
    ...(post.author.sameAs ? { sameAs: post.author.sameAs } : {}),
  }
  const publisher = {
    "@type": "Organization",
    name: "Gravitre",
    url: SITE_URL,
    logo: {
      "@type": "ImageObject",
      url: `${SITE_URL}/images/gravitre-logo-black.png`,
    },
  }

  const blogPosting = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    headline: post.title,
    description: post.description,
    image: post.heroImage ? `${SITE_URL}${post.heroImage}` : `${SITE_URL}/images/gravitre-logo-black.png`,
    datePublished: post.datePublished,
    dateModified: post.dateModified,
    author,
    publisher,
    keywords: post.keywords.join(", "),
    articleSection: post.category,
    url,
  }

  const breadcrumbs = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_URL}/blog` },
      { "@type": "ListItem", position: 3, name: post.title, item: url },
    ],
  }

  const faqPage = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: post.faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: { "@type": "Answer", text: faq.answer },
    })),
  }

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(blogPosting) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbs) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqPage) }} />
    </>
  )
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const post = getBlogPost(slug)
  if (!post) notFound()

  const { Content } = post

  return (
    <div className="bg-card">
      <ArticleJsonLd post={post} />

      <article className="px-6 pb-16 pt-28 lg:pt-32">
        <div className="mx-auto max-w-3xl">
          {/* Breadcrumb / back */}
          <nav aria-label="Breadcrumb" className="mb-8">
            <Link
              href="/blog"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to blog
            </Link>
          </nav>

          {/* Header */}
          <header>
            <span className="text-xs font-medium uppercase tracking-wider text-primary">{post.category}</span>
            <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              {post.title}
            </h1>
            <p className="mt-5 text-pretty text-lg leading-relaxed text-muted-foreground">{post.excerpt}</p>

            <div className="mt-6 flex flex-wrap items-center gap-4 border-b border-border pb-8">
              <AuthorAvatar name={post.author.name} className="h-11 w-11 text-sm" />
              <div className="mr-auto">
                <div className="text-sm font-medium text-foreground">{post.author.name}</div>
                <div className="text-xs text-muted-foreground">{post.author.role}</div>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" />
                  <time dateTime={post.datePublished}>{post.displayDate}</time>
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {post.readTime}
                </span>
              </div>
            </div>
          </header>

          {/* Hero image */}
          <figure className="mt-8 overflow-hidden rounded-2xl border border-border">
            {post.heroImage ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={post.heroImage}
                alt={post.heroAlt}
                width={1200}
                height={630}
                className="aspect-video w-full object-contain bg-muted/50"
              />
            ) : (
              <div
                className={`aspect-video w-full bg-gradient-to-br ${post.heroGradient ?? "from-primary/10 to-muted"} flex items-center justify-center px-8`}
                role="img"
                aria-label={post.heroAlt}
              >
                <span className="text-center text-sm font-medium uppercase tracking-wider text-primary/80">
                  {post.category}
                </span>
              </div>
            )}
          </figure>

          {/* Key takeaways: extractable summary for answer engines (AEO) */}
          <aside
            aria-label="Key takeaways"
            className="mt-10 rounded-2xl border border-emerald-100 bg-primary/10/60 p-6"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">Key takeaways</h2>
            <ul className="mt-4 flex flex-col gap-3">
              {post.takeaways.map((point) => (
                <li key={point} className="flex gap-3 text-sm leading-relaxed text-foreground">
                  <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/100" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </aside>

          {/* Body */}
          <div
            className="mt-10 text-lg leading-relaxed text-foreground [&>*:first-child]:mt-0 [&_a]:font-medium [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_h2]:mt-12 [&_h2]:text-pretty [&_h2]:text-2xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-foreground [&_p]:mt-6 [&_strong]:font-semibold [&_strong]:text-foreground [&_ul]:mt-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6"
          >
            <Content />
          </div>

          {/* FAQ: mirrors FAQPage schema for AEO rich results */}
          <section aria-labelledby="faq-heading" className="mt-16 border-t border-border pt-10">
            <h2 id="faq-heading" className="text-2xl font-semibold tracking-tight text-foreground">
              Frequently asked questions
            </h2>
            <dl className="mt-6 flex flex-col gap-6">
              {post.faqs.map((faq) => (
                <div key={faq.question} className="rounded-xl border border-border p-5">
                  <dt className="font-medium text-foreground">{faq.question}</dt>
                  <dd className="mt-2 text-muted-foreground">{faq.answer}</dd>
                </div>
              ))}
            </dl>
          </section>

          {/* Subtle conversion close */}
          <section className="mt-16 rounded-2xl border border-border bg-muted/50 p-8 text-center">
            <h2 className="text-pretty text-xl font-semibold text-foreground">
              Give your team the time back to do the work only they can do.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
              Gravitre&apos;s AI agents absorb the administrative drag, with a human always in the loop, so your people
              can focus on strategy, creativity, and relationships.
            </p>
            <Link
              href="/get-started"
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-primary/100"
            >
              Try Gravitre for free
              <ArrowRight className="h-4 w-4" />
            </Link>
          </section>
        </div>
      </article>
    </div>
  )
}
