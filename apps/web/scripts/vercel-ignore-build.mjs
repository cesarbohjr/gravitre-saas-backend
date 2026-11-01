// Vercel's convention is inverted: 0 skips, 1 builds. No dependencies needed.
// Compare with the previous successful deployment, never merely HEAD^: several
// pushes can arrive between builds, and an earlier frontend change must survive.
import { execFileSync } from "node:child_process"

function git(...args) {
  return execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim()
}

function main() {
  if (process.env.GRAVITRE_FORCE_WEB_BUILD === "1") return 1
  const previous = process.env.VERCEL_GIT_PREVIOUS_SHA || ""
  const current = process.env.VERCEL_GIT_COMMIT_SHA || ""
  if (![previous, current].every((sha) => /^[a-f0-9]{40}$/i.test(sha))) return 1

  // Commands work whether Vercel's Root Directory is the repo or apps/web.
  const root = git("rev-parse", "--show-toplevel")
  git("-C", root, "merge-base", "--is-ancestor", previous, current)
  const files = git("-C", root, "diff", "--name-only", "--no-renames", "-z", previous, current)
    .split("\0").filter(Boolean)
  // Unknown paths build. Public docs under apps/web/content remain build inputs.
  // The generated provider registry also reads this backend source file.
  const irrelevant = (file) => {
    if (file === "backend/app/connectors/managed_business_connectors.json") return false
    return /^(backend\/|docs\/|tests\/|e2e\/|\.github\/|\.cursor\/)/.test(file)
      || /^(README\.md|AGENTS\.md|LICENSE(?:\.md)?|CHANGELOG\.md)$/.test(file)
  }
  return files.every(irrelevant) ? 0 : 1
}

let decision = 1
try {
  decision = main()
} catch {
  // Missing/shallow Git history, force pushes or command errors must build.
}
console.log(decision === 0 ? "Skipping web build: no frontend build inputs changed." : "Building web: changed inputs or comparison unavailable.")
process.exitCode = decision
