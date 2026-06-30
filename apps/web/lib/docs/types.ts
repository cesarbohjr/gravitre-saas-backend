export type DocAudience = "public" | "internal"
export type DocDepth = "high" | "mid" | "deep"
export type DocTier = "all" | "free" | "node" | "control" | "command" | "enterprise"
export type DocStatus = "draft" | "review" | "published"

export interface DocFrontmatter {
  title: string
  description: string
  audience: DocAudience
  depth: DocDepth
  tier?: DocTier
  status?: DocStatus
  category?: string
  readTime?: string
  prev?: { title: string; href: string }
  next?: { title: string; href: string }
}

export interface DocEntry {
  slug: string
  frontmatter: DocFrontmatter
  content: string
  filePath: string
}
