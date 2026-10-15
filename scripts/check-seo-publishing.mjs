#!/usr/bin/env node
/** New-content SEO gate. Existing content debt is reported separately, not silently rewritten. */
import fs from "node:fs"
import { execFileSync } from "node:child_process"

const read = (p) => fs.readFileSync(p, "utf8")
const errors = []
const warnings = []
function changedFiles() {
  const base = process.env.SEO_BASE_REF || (process.env.GITHUB_BASE_REF ? `origin/${process.env.GITHUB_BASE_REF}` : "HEAD~1")
  try {
    return execFileSync("git", ["diff", "--name-only", "--diff-filter=ACMR", `${base}...HEAD`], { encoding:"utf8" }).trim().split("\n").filter(Boolean)
  } catch {
    // No comparison base in local checkout: scan all public docs; do not claim validation passed otherwise.
    warnings.push("No git diff base available; auditing all public MDX documents.")
    return []
  }
}
function collect(dir) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes:true }).flatMap(e => e.isDirectory() ? collect(`${dir}/${e.name}`) : [`${dir}/${e.name}`])
}
function plain(s) { return s.replace(/<[^>]+>/g, " ").replace(/\[[^\]]+\]\([^)]*\)/g," ").replace(/[#*_\x60]/g," ").replace(/\s+/g," ").trim() }
const allDocs = collect("apps/web/content/docs/public").filter(p => /\.mdx?$/.test(p))
const diff = changedFiles()
const docFiles = diff.length ? diff.filter(p => p.startsWith("apps/web/content/docs/public/") && /\.mdx?$/.test(p)) : allDocs

// New public routes must declare their own canonical metadata in a page or layout.
// Avoid applying this rule to previously published routes with unrelated edits.
let added = []
try {
  const base = process.env.SEO_BASE_REF || (process.env.GITHUB_BASE_REF ? `origin/${process.env.GITHUB_BASE_REF}` : "HEAD~1")
  added = execFileSync("git", ["diff", "--name-only", "--diff-filter=A", `${base}...HEAD`], {encoding:"utf8"}).trim().split("\n").filter(Boolean)
} catch { warnings.push("Cannot identify new routes for canonical enforcement.") }
for (const p of added) {
  if (!p.startsWith("apps/web/app/(marketing)/") || !p.endsWith("/page.tsx")) continue
  if (p.includes("[...") || p.includes("[slug]")) continue
  const layout = p.replace(/page\.tsx$/, "layout.tsx")
  const page = read(p)
  const layoutText = fs.existsSync(layout) ? read(layout) : ""
  if (!/canonical\s*:|canonical\s*=/.test(page + "\n" + layoutText)) {
    errors.push(`${p}: new public route must define a self-referencing canonical in page/layout metadata`)
  }
}
// Gate newly authored blog modules before publication. Link ownership/source quality
// still needs human review; distinct source domains are only a minimum signal.
for (const p of added.filter(p => /^apps\/web\/app\/\(marketing\)\/blog\/content\/[^/]+\.tsx$/.test(p))) {
  const body = read(p)
  for (const field of ["slug:", "title:", "description:", "author:", "datePublished:", "dateModified:", "heroAlt:"]) {
    if (!body.includes(field)) errors.push(`${p}: new blog post missing ${field}`)
  }
  // A new article should include at least one reader-question H2 with an
  // answer-led opening paragraph, not merely a list of generic headings.
  const questionSections = [...body.matchAll(/<h2[^>]*>([^<]*\?)<\/h2>\s*<p[^>]*>([\s\S]*?)<\/p>/g)]
  if (!questionSections.length) {
    errors.push(`${p}: include a question-form H2 followed immediately by a direct-answer paragraph`)
  } else if (questionSections.every(([, , para]) => plain(para).split(/\s+/).filter(Boolean).length < 8)) {
    errors.push(`${p}: question H2 needs a substantive first-sentence answer`)
  }
  // Advisory: extractable prose should name its subject without surrounding context.
  const openingParagraphs = [...body.matchAll(/<p(?:\\s[^>]*)?>\\s*([\\s\\S]*?)<\\/p>/g)]
  const contextOpenings = openingParagraphs.filter(([, content]) => /^(this|these|those|they|it|such an approach)\\b/i.test(plain(content)))
  if (contextOpenings.length) warnings.push(`${p}: ${contextOpenings.length} paragraph(s) open with ambiguous pronouns; name the subject in the first sentence`)
  const external = [...body.matchAll(/https?:\/\/[^\s"'\x60<>)]+/g)].map(m => {
    try { return new URL(m[0]).hostname } catch { return "" }
  }).filter(Boolean)
  const independentDomains = new Set(external.filter(h => !h.endsWith("gravitre.app")))
  if (independentDomains.size < 2) {
    errors.push(`${p}: add at least two independently verified external primary-source links before publication`)
  }
}
// Inventory duplicate public-doc titles so new docs cannot cannibalize existing pages.
const titlesByName = new Map()
for (const p of allDocs) {
  const raw = read(p)
  const fm = raw.match(/^---\s*\n([\s\S]*?)\n---/)
  if (!fm || !/^audience:\s*public\s*$/m.test(fm[1]) || /^status:\s*draft\s*$/m.test(fm[1])) continue
  const title = fm[1].match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1]?.trim().toLowerCase()
  if (!title) continue
  const paths = titlesByName.get(title) || []
  paths.push(p)
  titlesByName.set(title, paths)
}
for (const [title, paths] of titlesByName) {
  if (paths.length < 2) continue
  errors.push(`Duplicate public-doc title "${title}": ${paths.join(", ")}. Give each page a distinct search intent or plan a reviewed 301 redirect.`)
  for (const p of paths) {
    if (added.includes(p)) errors.push(`${p}: new doc duplicates an existing public title "${title}"`)
  }
}
// Intrinsic image size avoids CLS. Enforce for newly created marketing/blog JSX.
for (const p of added.filter(p => p.startsWith("apps/web/") && /\.(tsx|jsx)$/.test(p) && (p.includes("/(marketing)/") || p.includes("/marketing/")))) {
  const jsx = read(p)
  const imgTags = jsx.match(/<img\b[\s\S]*?>/g) || []
  for (const tag of imgTags) {
    if (!/\bwidth=/.test(tag) || !/\bheight=/.test(tag)) {
      errors.push(`${p}: img element needs intrinsic width and height, or use next/image`)
    }
  }
}
for(const p of docFiles){
  if (!fs.existsSync(p)) continue
  const raw = read(p)
  const match = raw.match(/^---\s*\n([\s\S]*?)\n---/)
  if(!match){errors.push(`${p}: YAML frontmatter required`);continue}
  const header=match[1]
  const value=(key)=>(header.match(new RegExp(`^${key}:\\s*["']?(.+?)["']?\\s*$`,"m"))||[])[1]?.trim()
  if (value("audience") !== "public" || value("status") === "draft") continue
  const title=value("title"), description=value("description")
  if(!title)errors.push(`${p}: missing title`)
  else if(title.length < 14 || title.length > 44)warnings.push(`${p}: title ${title.length} characters; final docs suffix may exceed search length`)
  if(!description)errors.push(`${p}: missing description`)
  else if(description.length < 110 || description.length > 160)warnings.push(`${p}: description ${description.length} characters; target 110-160`)
  const body=raw.slice(match[0].length)
  if(plain(body).split(/\s+/).length < 800)warnings.push(`${p}: under 800 words; verify it fully answers the query (not a hard SEO rule)`)
  if (!/\bhttps?:\/\//.test(body))warnings.push(`${p}: no primary-source hyperlinks; cite verified sources when making factual claims`)
}
const registry="apps/web/app/(marketing)/blog/posts.tsx"
if(diff.includes(registry) || diff.some(p=>p.startsWith("apps/web/app/(marketing)/blog/content/"))){
  const content=read(registry)
  if(!content.includes("dateModified") || !content.includes("datePublished"))warnings.push("Blog registry should retain genuine datePublished/dateModified for each published post.")
  warnings.push("Review new blog posts for named author, two independently verified primary-source links, question/answer opening, original examples, and non-templated structure.")
}
if (!fs.existsSync("apps/web/app/sitemap.ts")) errors.push("Missing marketing sitemap generator.")
for (const path of ["apps/web/app/(marketing)/docs/[...slug]/page.tsx","apps/web/app/(marketing)/blog/[slug]/page.tsx"]){
  const content=read(path)
  if(!content.includes("canonical"))errors.push(`${path}: missing canonical metadata`)
}
for (const message of warnings)console.warn("SEO ADVISORY:",message)
for (const message of errors)console.error("SEO ERROR:",message)
console.log(`SEO publishing gate: ${docFiles.length} changed public docs checked; ${errors.length} errors; ${warnings.length} advisories`)
if(errors.length)process.exit(1)
