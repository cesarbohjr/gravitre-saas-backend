import fs from "fs"
import path from "path"

import matter from "gray-matter"

import type { DocEntry, DocFrontmatter } from "./types"

const PUBLIC_DOCS_ROOT = path.join(process.cwd(), "content/docs/public")

function walkMdxFiles(dir: string, base = ""): string[] {
  if (!fs.existsSync(dir)) return []

  const entries = fs.readdirSync(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    const relative = base ? `${base}/${entry.name}` : entry.name
    const fullPath = path.join(dir, entry.name)

    if (entry.isDirectory()) {
      files.push(...walkMdxFiles(fullPath, relative))
      continue
    }

    if (entry.isFile() && (entry.name.endsWith(".mdx") || entry.name.endsWith(".md"))) {
      if (entry.name.startsWith("index.")) {
        files.push(base)
      } else {
        files.push(relative.replace(/\.(mdx|md)$/, ""))
      }
    }
  }

  return files
}

function resolveDocPath(slug: string): string | null {
  const candidates = [
    path.join(PUBLIC_DOCS_ROOT, `${slug}.mdx`),
    path.join(PUBLIC_DOCS_ROOT, `${slug}.md`),
    path.join(PUBLIC_DOCS_ROOT, slug, "index.mdx"),
    path.join(PUBLIC_DOCS_ROOT, slug, "index.md"),
  ]

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate
  }

  return null
}

function parseDoc(filePath: string, slug: string): DocEntry | null {
  const raw = fs.readFileSync(filePath, "utf8")
  const { data, content } = matter(raw)
  const frontmatter = data as DocFrontmatter

  if (frontmatter.audience !== "public") {
    return null
  }

  if (frontmatter.status === "draft") {
    return null
  }

  return {
    slug,
    frontmatter,
    content,
    filePath,
  }
}

export function getAllPublicDocSlugs(): string[] {
  return walkMdxFiles(PUBLIC_DOCS_ROOT).sort()
}

export function getPublicDocBySlug(slug: string): DocEntry | null {
  const normalized = slug.replace(/^\/+|\/+$/g, "")
  const filePath = resolveDocPath(normalized)
  if (!filePath) return null

  return parseDoc(filePath, normalized)
}

export function getPublishedPublicDocs(): DocEntry[] {
  return getAllPublicDocSlugs()
    .map((slug) => getPublicDocBySlug(slug))
    .filter((doc): doc is DocEntry => doc !== null)
}

export function getDocsNavSections() {
  const docs = getPublishedPublicDocs()

  const byCategory = new Map<string, DocEntry[]>()
  for (const doc of docs) {
    const category = doc.frontmatter.category ?? "Documentation"
    const list = byCategory.get(category) ?? []
    list.push(doc)
    byCategory.set(category, list)
  }

  return Array.from(byCategory.entries()).map(([title, items]) => ({
    title,
    items: items.map((doc) => ({
      title: doc.frontmatter.title,
      href: `/docs/${doc.slug}`,
    })),
  }))
}
