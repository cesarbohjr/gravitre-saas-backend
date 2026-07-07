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
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.08 }}
    >
      <Link
        href={`/blog/${post.slug}`}
        className="group flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-6 transition-all hover:border-emerald-300 hover:shadow-md"
      >
        <span className="text-xs font-medium uppercase tracking-wider text-emerald-600">{post.category}</span>
        <h3 className="mt-3 line-clamp-2 text-lg font-medium text-zinc-900 transition-colors group-hover:text-emerald-700">
          {post.title}
        </h3>
        <p className="mt-2 line-clamp-2 flex-1 text-sm text-zinc-500">{post.excerpt}</p>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-zinc-500">{post.author.name}</span>
          <span className="flex items-center gap-1 text-xs text-zinc-400">
            <Clock className="h-3 w-3" />
            {post.readTime}
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
    <div className="bg-white">
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">Blog</h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-600">
              Product updates, engineering deep dives, and insights on building the future of AI operations.
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
                      ? "bg-zinc-900 text-white"
                      : "border border-zinc-200 text-zinc-600 hover:border-zinc-300 hover:text-zinc-900"
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
              className="group block overflow-hidden rounded-2xl border border-zinc-200 bg-white transition-all hover:border-emerald-300 hover:shadow-lg"
            >
              <div className="grid lg:grid-cols-2">
                <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-emerald-100 to-zinc-100 lg:aspect-auto">
                  {featuredPost.heroImage ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={featuredPost.heroImage}
                      alt={featuredPost.heroAlt}
                      className="absolute inset-0 h-full w-full object-cover opacity-90 transition-opacity group-hover:opacity-100"
                    />
                  ) : (
                    <div
                      className={`absolute inset-0 bg-gradient-to-br ${featuredPost.heroGradient ?? "from-emerald-50 to-zinc-100"}`}
                      role="img"
                      aria-label={featuredPost.heroAlt}
                    />
                  )}
                </div>
                <div className="flex flex-col justify-center p-8 lg:p-10">
                  <span className="text-xs font-medium uppercase tracking-wider text-emerald-600">
                    {featuredPost.category} · Featured
                  </span>
                  <h2 className="mt-3 text-2xl font-semibold text-zinc-900 transition-colors group-hover:text-emerald-700">
                    {featuredPost.title}
                  </h2>
                  <p className="mt-3 line-clamp-2 text-zinc-600">{featuredPost.excerpt}</p>
                  <div className="mt-6 flex items-center gap-4">
                    <span
                      aria-hidden
                      className="grid h-10 w-10 place-items-center rounded-full bg-emerald-600 text-sm font-semibold text-white"
                    >
                      {authorInitials(featuredPost.author.name)}
                    </span>
                    <div>
                      <div className="text-sm font-medium text-zinc-900">{featuredPost.author.name}</div>
                      <div className="flex items-center gap-2 text-xs text-zinc-500">
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

      <section className="border-t border-zinc-200 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-8"
          >
            <h2 className="text-2xl font-semibold text-zinc-900">All Posts</h2>
          </motion.div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredPosts.map((post, i) => (
              <PostCard key={post.slug} post={post} index={i} />
            ))}
          </div>
          {filteredPosts.length === 0 && (
            <p className="py-12 text-center text-sm text-zinc-500">No posts in this category yet.</p>
          )}
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-zinc-50 px-6 py-24">
        <div className="mx-auto max-w-xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="mb-4 text-2xl font-semibold text-zinc-900">Subscribe to our newsletter</h2>
            <p className="mb-6 text-zinc-600">
              Get the latest posts, product updates, and AI insights delivered to your inbox.
            </p>
            <form className="flex gap-3">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              <button
                type="submit"
                className="rounded-lg bg-emerald-600 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-500"
              >
                Subscribe
              </button>
            </form>
            <p className="mt-3 text-xs text-zinc-500">No spam. Unsubscribe anytime.</p>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
