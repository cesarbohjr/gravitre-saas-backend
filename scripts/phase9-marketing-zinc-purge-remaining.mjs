/**
 * UI 2.0 backlog — purge remaining zinc-* utilities on marketing surfaces.
 * Class-name remaps only; does not invent prices/claims.
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

/** Longer / more specific pairs first. */
const pairs = [
  ["placeholder-zinc-500", "placeholder:text-muted-foreground"],
  ["shadow-zinc-900/25", "shadow-foreground/25"],
  ["shadow-zinc-900/20", "shadow-foreground/20"],
  ["shadow-zinc-900/5", "shadow-foreground/5"],
  ["shadow-zinc-900/10", "shadow-foreground/10"],
  ["from-zinc-900/10", "from-foreground/10"],
  ["from-zinc-900", "from-card"],
  ["to-zinc-950", "to-background"],
  ["to-zinc-900", "to-card"],
  ["via-zinc-100", "via-muted"],
  ["via-zinc-200", "via-muted"],
  ["from-zinc-200", "from-muted"],
  ["from-zinc-100", "from-muted"],
  ["from-zinc-600", "from-muted-foreground"],
  ["to-zinc-700", "to-muted-foreground"],
  ["to-zinc-200", "to-muted"],
  ["border-zinc-800", "border-border"],
  ["border-zinc-700", "border-border"],
  ["border-zinc-600", "border-border"],
  ["hover:border-zinc-700", "hover:border-border"],
  ["hover:border-zinc-600", "hover:border-border"],
  ["hover:bg-zinc-400", "hover:bg-muted-foreground/40"],
  ["bg-zinc-950", "bg-background"],
  ["bg-zinc-900", "bg-card"],
  ["bg-zinc-800", "bg-muted"],
  ["bg-zinc-700", "bg-muted"],
  ["bg-zinc-600", "bg-muted-foreground"],
  ["bg-zinc-400", "bg-muted-foreground"],
  ["bg-zinc-300", "bg-muted"],
  ["bg-zinc-200", "bg-muted"],
  ["bg-zinc-100", "bg-muted"],
  ["bg-zinc-50", "bg-muted/50"],
  ["text-zinc-200", "text-foreground"],
  ["text-zinc-300", "text-muted-foreground"],
  ["text-zinc-400", "text-muted-foreground"],
  ["text-zinc-500", "text-muted-foreground"],
  ["text-zinc-600", "text-muted-foreground"],
  ["text-zinc-700", "text-foreground"],
  ["text-zinc-800", "text-foreground"],
  ["text-zinc-900", "text-foreground"],
  ["ring-zinc-900", "ring-foreground"],
  ["divide-zinc-100", "divide-border"],
  ["divide-zinc-200", "divide-border"],
]

function walk(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, acc)
    else if (/\.(tsx|ts|jsx|js)$/.test(entry.name)) acc.push(full)
  }
  return acc
}

let files = []
for (const root of roots) {
  if (!fs.existsSync(root)) {
    console.error("missing root", root)
    process.exit(1)
  }
  files = files.concat(walk(root))
}

let changed = 0
const remaining = []
for (const file of files) {
  let source = fs.readFileSync(file, "utf8")
  const original = source
  for (const [from, to] of pairs) {
    if (source.includes(from)) source = source.split(from).join(to)
  }
  if (source !== original) {
    fs.writeFileSync(file, source)
    changed += 1
  }
  if (/zinc-/.test(source)) {
    remaining.push({
      file: path.relative(repoRoot, file),
      hits: [...source.matchAll(/zinc-[a-z0-9/[\]%.-]+/gi)].map((m) => m[0]),
    })
  }
}

console.log(
  JSON.stringify(
    {
      changed,
      remainingFiles: remaining.length,
      remainingSample: remaining.slice(0, 20).map((r) => ({
        file: r.file,
        hits: [...new Set(r.hits)].slice(0, 8),
      })),
    },
    null,
    2,
  ),
)
