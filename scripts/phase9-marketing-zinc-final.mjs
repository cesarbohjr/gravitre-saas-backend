/**
 * Final remnant zinc purge for marketing (opacity / placeholder / arbitrary shadows).
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
  ["placeholder-zinc-400", "placeholder:text-muted-foreground"],
  ["shadow-zinc-200/40", "shadow-border/40"],
  ["shadow-zinc-200/50", "shadow-border/50"],
  ["shadow-zinc-900/[0.04]", "shadow-foreground/5"],
  ["from-zinc-300", "from-border"],
  ["to-zinc-100", "to-muted"],
  ["from-emerald-100 to-muted", "from-primary/15 to-muted"],
  ["from-emerald-100 to-zinc-100", "from-primary/15 to-muted"],
  ["hover:border-zinc-400", "hover:border-border"],
  ["border-zinc-900", "border-foreground"],
  ["focus-visible:ring-zinc-500", "focus-visible:ring-ring"],
  ["via-primary/5 to-zinc-100", "via-primary/5 to-muted"],
  ["via-primary/5/40 to-zinc-100", "via-primary/5 to-muted"],
  ["to-emerald-400", "to-primary"],
]

function walk(dir, acc = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, acc)
    else if (/\.(tsx|ts)$/.test(entry.name)) acc.push(full)
  }
  return acc
}

let changed = 0
const remaining = []
for (const root of roots) {
  for (const file of walk(root)) {
    let source = fs.readFileSync(file, "utf8")
    const original = source
    for (const [from, to] of pairs) {
      if (source.includes(from)) source = source.split(from).join(to)
    }
    if (source !== original) {
      fs.writeFileSync(file, source)
      changed += 1
    }
    const hits = source.match(/zinc-[^\s"'`]+/g)
    if (hits) remaining.push({ file: path.relative(repoRoot, file), hits: [...new Set(hits)] })
  }
}

console.log(JSON.stringify({ changed, remaining }, null, 2))
