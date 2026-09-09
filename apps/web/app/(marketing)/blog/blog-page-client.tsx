"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { Clock } from "lucide-react"
import type { BlogPost } from "./types"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingPageHero, MarketingRails } from "@/components/marketing/nodus/page-shell"
import {
  BLOG_TRACE_STAGES,
  GravitreFlow,
  GravitreReveal,
  GravitreResolve,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system"

export type BlogCard = Pick<
  BlogPost,
  | "slug"
  | "title"
  | "excerpt"
  | "category"
  | "author"
  | "displayDate"
  | "readTime"
  | "heroImage"
  | "heroGradient"
  | "heroAlt"
>

function authorInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
}

function PostCard({ post, index }: { post: BlogCard; index: number }) {
  return (
    <GravitreFlow delay={index * 0.06}>
      <Link
        href={`/blog/${post.slug}`}
        className="group flex flex-col p-6 transition-colors hover:bg-gray-50"
      >
        <span className="text-xs font-medium uppercase tracking-wider text-primary">{post.category}</span>
        <h3 className="mt-2 line-clamp-2 text-lg font-medium text-foreground transition-colors group-hover:text-primary">
          {post.title}
        </h3>
        <p className="mt-2 line-clamp-2 text-sm text-gray-600">{post.excerpt}</p>
        <div className="mt-4 flex items-center justify-between gap-2 text-xs text-gray-500">
          <span>{post.author.name}</span>
          <span className="flex shrink-0 items-center gap-2">
            <span>{post.displayDate}</span>
            <span aria-hidden>·</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {post.readTime}
            </span>
          </span>
        </div>
      </Link>
    </GravitreFlow>
  )
}

type BlogPageClientProps = {
  featuredPost: BlogCard
  listingPosts: BlogCard[]
  categories: string[]
}

export function BlogPageClient({ featuredPost, listingPosts, categories }: BlogPageClientProps) {
  const [activeCategory, setActiveCategory] = useState("All")

  const filteredPosts = useMemo(() => {
    if (activeCategory === "All") return listingPosts
    return listingPosts.filter((post) => post.category === activeCategory)
  }, [activeCategory, listingPosts])

  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Blog"
        title="Writing from the field"
        description="Product updates, engineering deep dives, and how one AI brain coordinates real work."
      >
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
          {categories.map((category) => {
            const isActive = category === activeCategory
            return (
              <button
                key={category}
                type="button"
                onClick={() => setActiveCategory(category)}
                className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                  isActive
                    ? "bg-foreground text-white"
                    : "border border-border text-muted-foreground hover:border-border hover:text-foreground"
                }`}
              >
                {category}
              </button>
            )
          })}
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Field evidence"
          title="Field → Evidence → Outcome"
          description="How we write — from what we see in production, through evidence you can verify, to outcomes teams can act on."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={BLOG_TRACE_STAGES}
            gradientId="blog-trace"
            ariaLabel="Blog path from Field through Evidence to Outcome"
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <GravitreResolve className="mb-16">
          <Link
            href={`/blog/${featuredPost.slug}`}
            className="group block overflow-hidden border border-border divide-y hover:bg-gray-50 transition-colors"
          >
            <div className="grid lg:grid-cols-2">
              <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-primary/15 to-gray-50 lg:aspect-auto">
                {featuredPost.heroImage ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={featuredPost.heroImage}
                    alt={featuredPost.heroAlt}
                    className="absolute inset-0 h-full w-full object-cover opacity-90 transition-opacity group-hover:opacity-100"
                  />
                ) : (
                  <div
                    className={`absolute inset-0 bg-gradient-to-br ${featuredPost.heroGradient ?? "from-primary/10 to-gray-50"}`}
                    role="img"
                    aria-label={featuredPost.heroAlt}
                  />
                )}
              </div>
              <div className="flex flex-col justify-center p-8 lg:p-10">
                <span className="text-xs font-medium uppercase tracking-wider text-primary">
                  {featuredPost.category} · Featured
                </span>
                <h2 className="mt-3 text-2xl font-semibold text-foreground transition-colors group-hover:text-primary">
                  {featuredPost.title}
                </h2>
                <p className="mt-3 line-clamp-2 text-muted-foreground">{featuredPost.excerpt}</p>
                <div className="mt-6 flex items-center gap-4">
                  <span
                    aria-hidden
                    className="grid h-10 w-10 place-items-center rounded-full bg-primary text-sm font-semibold text-white"
                  >
                    {authorInitials(featuredPost.author.name)}
                  </span>
                  <div>
                    <div className="text-sm font-medium text-foreground">{featuredPost.author.name}</div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{featuredPost.displayDate}</span>
                      <span>·</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {featuredPost.readTime}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Link>
        </GravitreResolve>

        <div className="border-t border-border pt-12">
          <GravitreReveal className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground">All Posts</h2>
          </GravitreReveal>
          <div className="grid gap-4 border border-border divide-y">
            {filteredPosts.map((post, i) => (
              <PostCard key={post.slug} post={post} index={i} />
            ))}
          </div>
          {filteredPosts.length === 0 && (
            <p className="py-12 text-center text-sm text-muted-foreground">No posts in this category yet.</p>
          )}
        </div>
      </MarketingRails>
    </div>
  )
}
