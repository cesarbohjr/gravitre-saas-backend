"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Clock } from "lucide-react"

const featuredPost = {
  slug: "introducing-ai-operator-2",
  title: "Introducing AI Operator 2.0: Multi-Agent Orchestration",
  excerpt: "Today we're excited to announce AI Operator 2.0, featuring multi-agent orchestration, improved reasoning, and 10x faster task execution.",
  author: {
    name: "Sarah Chen",
    role: "CEO",
    image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=100&h=100&fit=crop&crop=face",
  },
  date: "April 2, 2026",
  readTime: "8 min read",
  category: "Product",
  image: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&h=600&fit=crop",
}

const posts = [
  {
    slug: "security-first-approach",
    title: "Our Security-First Approach to AI Automation",
    excerpt: "Learn how Gravitre protects your data with end-to-end encryption, role-based access control, and comprehensive audit trails.",
    author: { name: "Alex Kim", role: "Head of Security" },
    date: "March 28, 2026",
    readTime: "4 min read",
    category: "Security",
  },
  {
    slug: "workflow-templates-library",
    title: "Introducing 50+ Pre-Built Workflow Templates",
    excerpt: "Get started faster with our new library of workflow templates for sales, marketing, finance, and operations use cases.",
    author: { name: "Priya Patel", role: "VP Design" },
    date: "March 21, 2026",
    readTime: "5 min read",
    category: "Product",
  },
  {
    slug: "case-study-acme-corp",
    title: "How Acme Corp Reduced Manual Tasks by 80%",
    excerpt: "Learn how Acme Corp transformed their operations team with AI-powered automation, saving 2,000+ hours per month.",
    author: { name: "Emily Watson", role: "VP Product" },
    date: "March 15, 2026",
    readTime: "10 min read",
    category: "Case Study",
  },
  {
    slug: "enterprise-ai-governance",
    title: "The Complete Guide to Enterprise AI Governance",
    excerpt: "Best practices for implementing AI governance frameworks that balance innovation with compliance and risk management.",
    author: { name: "Marcus Rodriguez", role: "CTO" },
    date: "March 8, 2026",
    readTime: "12 min read",
    category: "Engineering",
  },
  {
    slug: "series-b-announcement",
    title: "Announcing Our $80M Series B",
    excerpt: "We're thrilled to announce our $80M Series B led by Andreessen Horowitz to accelerate our mission of AI-powered operations.",
    author: { name: "Sarah Chen", role: "CEO" },
    date: "February 28, 2026",
    readTime: "6 min read",
    category: "Company",
  },
  {
    slug: "ai-agent-best-practices",
    title: "10 Best Practices for Building Reliable AI Agents",
    excerpt: "Lessons learned from deploying thousands of AI agents: testing, monitoring, error handling, and continuous improvement.",
    author: { name: "David Kim", role: "VP Engineering" },
    date: "February 20, 2026",
    readTime: "8 min read",
    category: "Engineering",
  },
]

const categories = ["All", "Product", "Engineering", "Company", "Case Study", "Security"]

export default function BlogPage() {
  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
              Blog
            </h1>
            <p className="mt-6 text-lg text-zinc-600 max-w-2xl mx-auto">
              Product updates, engineering deep dives, and insights on building the future of AI operations.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Categories */}
      <section className="px-6 pb-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-wrap items-center gap-2">
            {categories.map((category, i) => (
              <button
                key={category}
                className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                  i === 0
                    ? "bg-zinc-900 text-white"
                    : "border border-zinc-200 text-zinc-600 hover:text-zinc-900 hover:border-zinc-300"
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Post */}
      <section className="px-6 pb-16">
        <div className="mx-auto max-w-5xl">
          <motion.a
            href={`/blog/${featuredPost.slug}`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="group block rounded-2xl border border-zinc-200 bg-white overflow-hidden transition-all hover:border-emerald-300 hover:shadow-lg"
          >
            <div className="grid lg:grid-cols-2">
              <div className="aspect-video lg:aspect-auto bg-gradient-to-br from-emerald-100 to-zinc-100 relative overflow-hidden">
                <img 
                  src={featuredPost.image} 
                  alt={featuredPost.title}
                  className="absolute inset-0 w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
                />
              </div>
              <div className="p-8 lg:p-10 flex flex-col justify-center">
                <span className="text-xs font-medium text-emerald-600 uppercase tracking-wider">
                  {featuredPost.category} - Featured
                </span>
                <h2 className="mt-3 text-2xl font-semibold text-zinc-900 group-hover:text-emerald-700 transition-colors">
                  {featuredPost.title}
                </h2>
                <p className="mt-3 text-zinc-600 line-clamp-2">
                  {featuredPost.excerpt}
                </p>
                <div className="mt-6 flex items-center gap-4">
                  <img
                    src={featuredPost.author.image}
                    alt={featuredPost.author.name}
                    className="h-10 w-10 rounded-full object-cover"
                  />
                  <div>
                    <div className="text-sm font-medium text-zinc-900">{featuredPost.author.name}</div>
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                      <span>{featuredPost.date}</span>
                      <span>-</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {featuredPost.readTime}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.a>
        </div>
      </section>

      {/* All Posts */}
      <section className="px-6 py-16 border-t border-zinc-200">
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
            {posts.map((post, i) => (
              <motion.a
                key={post.slug}
                href={`/blog/${post.slug}`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="group rounded-xl border border-zinc-200 bg-white p-6 transition-all hover:border-emerald-300 hover:shadow-md"
              >
                <span className="text-xs font-medium text-emerald-600 uppercase tracking-wider">
                  {post.category}
                </span>
                <h3 className="mt-3 text-lg font-medium text-zinc-900 group-hover:text-emerald-700 transition-colors line-clamp-2">
                  {post.title}
                </h3>
                <p className="mt-2 text-sm text-zinc-500 line-clamp-2">
                  {post.excerpt}
                </p>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs text-zinc-500">{post.author.name}</span>
                  <span className="flex items-center gap-1 text-xs text-zinc-400">
                    <Clock className="h-3 w-3" />
                    {post.readTime}
                  </span>
                </div>
              </motion.a>
            ))}
          </div>

          {/* Load More */}
          <div className="mt-12 text-center">
            <button className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition-all hover:bg-zinc-100">
              Load more posts
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Newsletter */}
      <section className="px-6 py-24 border-t border-zinc-200 bg-zinc-50">
        <div className="mx-auto max-w-xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-zinc-900 mb-4">Subscribe to our newsletter</h2>
            <p className="text-zinc-600 mb-6">
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
            <p className="mt-3 text-xs text-zinc-500">
              No spam. Unsubscribe anytime.
            </p>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
