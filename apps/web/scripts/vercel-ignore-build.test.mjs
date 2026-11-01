import { execFileSync, spawnSync } from "node:child_process"
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"
import assert from "node:assert/strict"
import test from "node:test"

const script = fileURLToPath(new URL("./vercel-ignore-build.mjs", import.meta.url))
test("build decisions preserve frontend changes across pushes and fail open", () => {
  const repo = mkdtempSync(path.join(tmpdir(), "gravitre-build-filter-"))
  const git = (...args) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8", stdio: "pipe" }).trim()
  const commit = (file) => {
    mkdirSync(path.dirname(path.join(repo, file)), { recursive: true })
    writeFileSync(path.join(repo, file), `${file}\n${Date.now()}\n`)
    git("add", "--", file)
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    return git("rev-parse", "HEAD")
  }
  const check = (previous, current, expected, extra = {}, cwd = repo) => {
    const result = spawnSync(process.execPath, [script], {
      cwd, encoding: "utf8", env: { ...process.env, GRAVITRE_FORCE_WEB_BUILD: "", VERCEL_GIT_PREVIOUS_SHA: previous, VERCEL_GIT_COMMIT_SHA: current, ...extra },
    })
    assert.equal(result.status, expected, result.stdout + result.stderr)
  }
  try {
    git("init")
    const base = commit("package.json")
    const docs = commit("docs/internal.md")
    const backend = commit("backend/app/service.py")
    check(base, docs, 0)
    check(base, backend, 0)
    check(base, backend, 1, { GRAVITRE_FORCE_WEB_BUILD: "1" })
    const frontend = commit("apps/web/app/page.tsx")
    check(backend, frontend, 1)
    const laterDocs = commit("docs/later.md")
    check(backend, laterDocs, 1) // don't skip an earlier unbuilt frontend push
    check(frontend, laterDocs, 0)
    check(frontend, laterDocs, 0, {}, path.join(repo, "apps/web"))
    const publicDocs = commit("apps/web/content/docs/public/guide.mdx")
    check(laterDocs, publicDocs, 1)
    const lock = commit("pnpm-lock.yaml")
    check(publicDocs, lock, 1)
    const shared = commit("packages/shared/index.ts")
    check(lock, shared, 1)
    const registry = commit("backend/app/connectors/managed_business_connectors.json")
    check(shared, registry, 1)
    git("rm", "--", "apps/web/app/page.tsx")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "remove page")
    check(registry, git("rev-parse", "HEAD"), 1)
    check("", registry, 1)
    check("invalid", registry, 1)
    check("a".repeat(40), registry, 1)
    check(registry, base, 1) // force-push/non-ancestor
  } finally {
    rmSync(repo, { recursive: true, force: true })
  }
})
