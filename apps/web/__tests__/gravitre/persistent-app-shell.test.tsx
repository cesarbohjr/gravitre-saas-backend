// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, relative, resolve } from "node:path"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  AppShellHostProvider,
  useAppShellHost,
  useAppShellOptions,
  useInsideAppShell,
} from "@/components/gravitre/app-shell-context"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const webRoot = resolve(__dirname, "../..")

function Host({ children }: { children: React.ReactNode }) {
  const { host, options } = useAppShellHost()
  return (
    <AppShellHostProvider host={host}>
      <header data-title={options.title ?? ""} data-fill={String(Boolean(options.fillViewport))} />
      {children}
    </AppShellHostProvider>
  )
}

function Page({ title, fillViewport }: { title?: string; fillViewport?: boolean }) {
  useAppShellOptions({ title, fillViewport })
  return <p>{title}</p>
}

function InsideProbe() {
  return <span data-inside={String(useInsideAppShell())} />
}

let root: Root
let container: HTMLDivElement
beforeEach(() => {
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const header = () => container.querySelector("header")!

describe("persistent app shell options", () => {
  it("takes the mounted page's title and follows navigation without remounting the host", () => {
    act(() => root.render(<Host><Page title="Agents" /></Host>))
    const first = header()
    expect(first.dataset.title).toBe("Agents")

    act(() => root.render(<Host><Page key="workflows" title="Workflows" fillViewport /></Host>))
    expect(header()).toBe(first)
    expect(header().dataset.title).toBe("Workflows")
    expect(header().dataset.fill).toBe("true")

    act(() => root.render(<Host>{null}</Host>))
    expect(header().dataset.title).toBe("")
    expect(header().dataset.fill).toBe("false")
  })

  it("updates a title that resolves after data loads in place", () => {
    act(() => root.render(<Host><Page title="Agent" /></Host>))
    act(() => root.render(<Host><Page title="Ada" /></Host>))
    expect(header().dataset.title).toBe("Ada")
  })

  it("reports whether a persistent host is mounted above", () => {
    act(() => root.render(<InsideProbe />))
    expect(container.querySelector("span")!.dataset.inside).toBe("false")
    act(() => root.render(<Host><InsideProbe /></Host>))
    expect(container.querySelector("span")!.dataset.inside).toBe("true")
  })
})

function walk(dir: string, excluded: Set<string>, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (excluded.has(full)) continue
    if (entry.isDirectory()) walk(full, excluded, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(full)
  }
  return out
}

function shellOffenders(appDir: string): string[] {
  // The old scanner walked every allowed app page before filtering it out,
  // issuing a stat for every entry. Under CI contention this exceeded 5s.
  // Prune only the same two root subtrees the original assertion exempted;
  // a nested marketing/(app) directory remains subject to the guard.
  return walk(appDir, new Set([join(appDir, "(app)"), join(appDir, "e2e")]))
    .filter((file) => /<AppShell[\s>]/.test(readFileSync(file, "utf8")))
    .map((file) => relative(appDir, file))
    .sort()
}

describe("route-group shell coverage", () => {
  it("mounts the shell once in app/(app)/layout.tsx", () => {
    const layout = readFileSync(resolve(webRoot, "app/(app)/layout.tsx"), "utf8")
    expect(layout).toMatch(/<PersistentAppShell>/)
  })

  it("only renders per-page <AppShell> under the (app) group or the /e2e screenshot harness", () => {
    expect(shellOffenders(resolve(webRoot, "app"))).toEqual([])
  })

  it("still catches forbidden shell routes outside the two allowed root subtrees", () => {
    const appDir = mkdtempSync(join(tmpdir(), "gravitre-shell-coverage-"))
    try {
      for (const route of ["(app)/page.tsx", "e2e/page.tsx", "marketing/page.tsx", "marketing/(app)/nested.tsx"]) {
        const file = resolve(appDir, route)
        mkdirSync(resolve(file, ".."), { recursive: true })
        writeFileSync(file, "export default () => <AppShell />")
      }
      expect(shellOffenders(appDir)).toEqual([
        join("marketing", "(app)", "nested.tsx"), join("marketing", "page.tsx"),
      ].sort())
    } finally {
      rmSync(appDir, { recursive: true, force: true })
    }
  })

  it("keeps marketing, auth, onboarding and welcome routes outside the shell group", () => {
    const groupRoutes = readdirSync(resolve(webRoot, "app/(app)"))
    for (const shellFree of ["login", "auth", "onboarding", "welcome", "get-started", "pricing"]) {
      expect(groupRoutes).not.toContain(shellFree)
    }
  })
})
