#!/usr/bin/env node
/**
 * Determine published canonical URLs from files changed in a release.
 * This emits suggestions only; ping-indexnow.mjs verifies actual publication.
 */
import fs from "node:fs"
import { execFileSync } from "node:child_process"

const base = process.env.SEO_BASE_REF || "HEAD~1"
const changed = execFileSync("git", ["diff", "--name-only", "--diff-filter=ACMR", `${base}...HEAD`], { encoding: "utf8" })
  .trim().split("\n").filter(Boolean)
const urls = new Set()
for (const file of changed) {
  if (file.startsWith("apps/web/content/docs/public/") && /\.(mdx|md)$/.test(file)) {
    const rel = file.slice("apps/web/content/docs/public/".length).replace(/\.(mdx|md)$/, "").replace(/\/index$/, "")
    urls.add(`https://gravitre.app/docs/${rel}`)
  }
  if (/^apps\/web\/app\/\(marketing\)\/blog\/content\/[^/]+\.tsx$/.test(file) && fs.existsSync(file)) {
    const slug = fs.readFileSync(file, "utf8").match(/\bslug:\s*["']([a-z0-9-]+)["']/)?.[1]
    if (slug) urls.add(`https://gravitre.app/blog/${slug}`)
  }
}
for (const url of urls) console.log(url)
