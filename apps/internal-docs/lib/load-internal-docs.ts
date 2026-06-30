import fs from "fs"
import path from "path"

import matter from "gray-matter"

const INTERNAL_ROOT = path.join(process.cwd(), "../../docs/internal")

export interface InternalDoc {
  slug: string
  title: string
  description: string
  category: string
  content: string
}

function walkMarkdown(dir: string, base = ""): string[] {
  if (!fs.existsSync(dir)) return []
  const out: string[] = []

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = base ? `${base}/${entry.name}` : entry.name
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...walkMarkdown(full, rel))
    } else if (entry.name.endsWith(".md") && entry.name.toLowerCase() !== "readme.md") {
      out.push(rel.replace(/\.md$/, ""))
    }
  }

  return out
}

function resolvePath(slug: string): string | null {
  const candidates = [
    path.join(INTERNAL_ROOT, `${slug}.md`),
    path.join(INTERNAL_ROOT, slug, "index.md"),
  ]
  for (const c of candidates) {
    if (fs.existsSync(c)) return c
  }
  return null
}

export function getInternalDocSlugs(): string[] {
  return walkMarkdown(INTERNAL_ROOT).sort()
}

export function getInternalDoc(slug: string): InternalDoc | null {
  const filePath = resolvePath(slug)
  if (!filePath) return null

  const raw = fs.readFileSync(filePath, "utf8")
  const { data, content } = matter(raw)

  if (data.audience !== "internal") return null
  if (data.status === "draft") return null

  return {
    slug,
    title: String(data.title ?? slug),
    description: String(data.description ?? ""),
    category: String(data.category ?? "Internal"),
    content,
  }
}

export function listInternalDocs(): InternalDoc[] {
  return getInternalDocSlugs()
    .map((slug) => getInternalDoc(slug))
    .filter((doc): doc is InternalDoc => doc !== null)
}
