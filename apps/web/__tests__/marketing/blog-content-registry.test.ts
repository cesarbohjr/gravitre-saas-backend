import { existsSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"
import {
  getAllBlogSlugs,
  getBlogPost,
  getFeaturedBlogPost,
  blogPosts,
} from "@/app/(marketing)/blog/posts"

const MSP_BLOG_SLUG = "governed-ai-for-msps"
const MSP_HERO_PUBLIC_PATH = "images/blog/governed-ai-for-msps-hero.jpg"

describe("marketing blog content registry", () => {
  it("registers the MSP monetization post with a static route slug", () => {
    expect(getAllBlogSlugs()).toContain(MSP_BLOG_SLUG)
    const post = getBlogPost(MSP_BLOG_SLUG)
    expect(post).toBeDefined()
    expect(post?.slug).toBe(MSP_BLOG_SLUG)
    expect(post?.title).toMatch(/MSP/i)
  })

  it("ships the MSP post hero asset referenced from the registry", () => {
    const post = getBlogPost(MSP_BLOG_SLUG)
    expect(post?.heroImage).toBe(`/${MSP_HERO_PUBLIC_PATH}`)
    expect(existsSync(join(process.cwd(), "public", MSP_HERO_PUBLIC_PATH))).toBe(true)
  })

  it("surfaces the MSP post on the blog index as the newest featured article", () => {
    expect(blogPosts.some((p) => p.slug === MSP_BLOG_SLUG)).toBe(true)
    expect(getFeaturedBlogPost().slug).toBe(MSP_BLOG_SLUG)
  })
})

describe("blog publishing metadata invariants", () => {
  it("keeps canonical slugs and article titles unique", () => {
    const slugs = blogPosts.map((post) => post.slug)
    const titles = blogPosts.map((post) => post.title.trim().toLocaleLowerCase("en-US"))
    expect(new Set(slugs).size).toBe(slugs.length)
    expect(new Set(titles).size).toBe(titles.length)
  })

  it("keeps real author attribution, descriptions, and publication dates", () => {
    for (const post of blogPosts) {
      expect(post.slug, "slug").toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
      expect(post.title.length, post.slug).toBeGreaterThan(10)
      expect(post.description.trim(), post.slug).not.toBe("")
      expect(post.description.length, `${post.slug}: meta description`).toBeGreaterThanOrEqual(110)
      expect(post.description.length, `${post.slug}: meta description`).toBeLessThanOrEqual(160)
      const renderedTitle = `${post.seoTitle ?? post.title} | Gravitre Blog`
      expect(renderedTitle.length, `${post.slug}: rendered title`).toBeGreaterThanOrEqual(30)
      expect(renderedTitle.length, `${post.slug}: rendered title`).toBeLessThanOrEqual(60)
      expect(post.author.name.trim(), post.slug).not.toBe("")
      expect(post.author.role.trim(), post.slug).not.toBe("")
      expect(Number.isNaN(Date.parse(post.datePublished)), post.slug).toBe(false)
      expect(Number.isNaN(Date.parse(post.dateModified)), post.slug).toBe(false)
      expect(new Date(post.dateModified).getTime(), post.slug).toBeGreaterThanOrEqual(new Date(post.datePublished).getTime())
      expect(post.heroAlt.trim(), post.slug).not.toBe("")
    }
  })
})
