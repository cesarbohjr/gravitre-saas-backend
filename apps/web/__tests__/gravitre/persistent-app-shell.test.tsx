// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { readdirSync, readFileSync, statSync } from "node:fs"
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

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.tsx?$/.test(name)) out.push(full)
  }
  return out
}

describe("route-group shell coverage", () => {
  it("mounts the shell once in app/(app)/layout.tsx", () => {
    const layout = readFileSync(resolve(webRoot, "app/(app)/layout.tsx"), "utf8")
    expect(layout).toMatch(/<PersistentAppShell>/)
  })

  it("only renders per-page <AppShell> under the (app) group or the /e2e screenshot harness", () => {
    const offenders = walk(resolve(webRoot, "app"))
      .map((file) => relative(webRoot, file))
      .filter((rel) => !/^app[\\/](\(app\)|e2e)[\\/]/.test(rel))
      .filter((rel) => /<AppShell[\s>]/.test(readFileSync(resolve(webRoot, rel), "utf8")))
    expect(offenders).toEqual([])
  })

  it("keeps marketing, auth, onboarding and welcome routes outside the shell group", () => {
    const groupRoutes = readdirSync(resolve(webRoot, "app/(app)"))
    for (const shellFree of ["login", "auth", "onboarding", "welcome", "get-started", "pricing"]) {
      expect(groupRoutes).not.toContain(shellFree)
    }
  })
})
