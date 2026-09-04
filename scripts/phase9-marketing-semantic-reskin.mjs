/**
 * Phase 9 tranche 2 — bulk zinc/emerald → semantic tokens on marketing surfaces.
 * Does not invent prices/claims; class-name remaps only.
 */
import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, "..")

const roots = [
  path.join(repoRoot, "apps", "web", "app", "(marketing)"),
  path.join(repoRoot, "apps", "web", "components", "marketing"),
]

const pairs = [
  ["text-zinc-900", "text-foreground"],
  ["text-zinc-800", "text-foreground"],
  ["text-zinc-700", "text-foreground"],
  ["text-zinc-600", "text-muted-foreground"],
  ["text-zinc-500", "text-muted-foreground"],
  ["text-zinc-400", "text-muted-foreground"],
  ["text-zinc-300", "text-muted-foreground"],
  ["bg-zinc-950", "bg-foreground"],
  ["bg-zinc-900", "bg-foreground"],
  ["bg-zinc-800", "bg-foreground/90"],
  ["bg-zinc-100", "bg-muted"],
  ["bg-zinc-50", "bg-muted/50"],
  ["border-zinc-300", "border-border"],
  ["border-zinc-200", "border-border"],
  ["border-zinc-100", "border-border"],
  ["hover:bg-zinc-100", "hover:bg-muted"],
  ["hover:bg-zinc-50", "hover:bg-muted/50"],
  ["hover:text-zinc-900", "hover:text-foreground"],
  ["hover:text-zinc-800", "hover:text-foreground"],
  ["hover:border-zinc-300", "hover:border-border"],
  ["divide-zinc-200", "divide-border"],
  ["ring-zinc-200", "ring-border"],
  ["from-zinc-50", "from-muted/50"],
  ["to-zinc-50", "to-muted/50"],
  ["via-zinc-50", "via-muted/50"],
  ["bg-emerald-50", "bg-primary/10"],
  ["bg-emerald-100", "bg-primary/15"],
  ["bg-emerald-500", "bg-primary"],
  ["bg-emerald-600", "bg-primary"],
  ["bg-emerald-700", "bg-primary"],
  ["text-emerald-900", "text-primary"],
  ["text-emerald-800", "text-primary"],
  ["text-emerald-700", "text-primary"],
  ["text-emerald-600", "text-primary"],
  ["text-emerald-500", "text-primary"],
  ["border-emerald-200", "border-primary/20"],
  ["border-emerald-300", "border-primary/30"],
  ["border-emerald-500", "border-primary"],
  ["from-emerald-50", "from-primary/10"],
  ["via-emerald-50", "via-primary/5"],
  ["to-emerald-50", "to-primary/10"],
  ["from-emerald-500", "from-primary"],
  ["via-emerald-500", "via-primary"],
  ["to-emerald-500", "to-primary"],
  ["ring-emerald-500", "ring-primary"],
  ["hover:bg-emerald-50", "hover:bg-primary/10"],
  ["hover:bg-emerald-600", "hover:bg-primary"],
  ["hover:text-emerald-700", "hover:text-primary"],
  ["hover:text-emerald-600", "hover:text-primary"],
]

function walk(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, acc)
    else if (/\.(tsx|ts|jsx|js)$/.test(entry.name)) acc.push(full)
  }
  return acc
}

function shouldSkip(file) {
  const norm = file.replace(/\\/g, "/")
  if (norm.endsWith("components/marketing/marketing-chrome.tsx")) return true
  if (norm.endsWith("app/(marketing)/page.tsx")) return true
  return false
}

let files = []
for (const root of roots) {
  if (!fs.existsSync(root)) {
    console.error("missing root", root)
    process.exit(1)
  }
  files = files.concat(walk(root))
}
files = files.filter((f) => !shouldSkip(f))

let changed = 0
const touched = []
for (const file of files) {
  let source = fs.readFileSync(file, "utf8")
  const original = source
  for (const [from, to] of pairs) {
    if (source.includes(from)) source = source.split(from).join(to)
  }
  source = source.replace(/\bbg-white\b/g, "bg-card")
  source = source.replace(/\bhover:bg-white\b/g, "hover:bg-card")
  if (source !== original) {
    fs.writeFileSync(file, source)
    changed += 1
    touched.push(path.relative(repoRoot, file))
  }
}

console.log(JSON.stringify({ scanned: files.length, changed, sample: touched.slice(0, 25) }, null, 2))
