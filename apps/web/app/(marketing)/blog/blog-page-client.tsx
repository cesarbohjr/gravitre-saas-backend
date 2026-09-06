"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Clock } from "lucide-react"
import type { BlogPost } from "./types"

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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
    >
      <Link
        href={`/blog/${post.slug}`}
        className="group flex h-full flex-col rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-md"
      >
        <span className="text-xs font-medium uppercase tracking-wider text-primary">{post.category}</span>
        <h3 className="mt-3 line-clamp-2 text-lg font-medium text-foreground transition-colors group-hover:text-primary">
          {post.title}
        </h3>
        <p className="mt-2 line-clamp-2 flex-1 text-sm text-muted-foreground">{post.excerpt}</p>
        <div className="mt-4 flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">{post.author.name}</span>
          <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
            <span>{post.displayDate}</span>
            <span aria-hidden>·</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {post.readTime}
            </span>
          </span>
        </div>
      </Link>
    </motion.div>
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
    <div className="bg-card">
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">Blog</h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
              Product updates, engineering deep dives, and how one AI brain coordinates real work.
            </p>
          </motion.div>
        </div>
      </section>

      <section className="px-6 pb-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-wrap items-center gap-2">
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
        </div>
      </section>

      <section className="px-6 pb-16">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Link
              href={`/blog/${featuredPost.slug}`}
              className="group block overflow-hidden rounded-2xl border border-border bg-card transition-all hover:border-primary/30 hover:shadow-lg"
            >
              <div className="grid lg:grid-cols-2">
                <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-primary/15 to-muted lg:aspect-auto">
                  {featuredPost.heroImage ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={featuredPost.heroImage}
                      alt={featuredPost.heroAlt}
                      className="absolute inset-0 h-full w-full object-cover opacity-90 transition-opacity group-hover:opacity-100"
                    />
                  ) : (
                    <div
                      className={`absolute inset-0 bg-gradient-to-br ${featuredPost.heroGradient ?? "from-primary/10 to-muted"}`}
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
          </motion.div>
        </div>
      </section>

      <section className="border-t border-border px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <h2 className="text-2xl font-semibold text-foreground">All Posts</h2>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredPosts.map((post, i) => (
              <PostCard key={post.slug} post={post} index={i} />
            ))}
          </div>
          {filteredPosts.length === 0 && (
            <p className="py-12 text-center text-sm text-muted-foreground">No posts in this category yet.</p>
          )}
        </div>
      </section>

      <section className="border-t border-border bg-muted/50 px-6 py-24">
        <div className="mx-auto max-w-xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="mb-4 text-2xl font-semibold text-foreground">Subscribe to our newsletter</h2>
            <p className="mb-6 text-muted-foreground">
              Get the latest posts, product updates, and AI insights delivered to your inbox.
            </p>
            <form className="flex gap-3">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                type="submit"
                className="rounded-lg bg-primary px-6 py-3 text-sm font-medium text-white transition-all hover:bg-primary/100"
              >
                Subscribe
              </button>
            </form>
            <p className="mt-3 text-xs text-muted-foreground">No spam. Unsubscribe anytime.</p>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
