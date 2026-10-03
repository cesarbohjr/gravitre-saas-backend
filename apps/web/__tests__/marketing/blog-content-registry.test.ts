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
