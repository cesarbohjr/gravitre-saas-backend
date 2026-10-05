// @vitest-environment jsdom
import React, { act, useContext } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { AuthContext } from "@/lib/auth-context"
import { ShotAuthProvider } from "@/app/e2e/shots/shot-auth"
import { GravitreAIWorkspaceHost } from "@/components/gravitre/ai-workspace-host"

const state = vi.hoisted(() => ({ pathname: "/e2e/shots/ai" }))
vi.mock("@/components/gravitre/ai-workspace-provider", () => ({ useGravitreAIWorkspace: () => ({ floatWorkspaceOpen: true, pageContext: { pathname: state.pathname } }) }))
vi.mock("@/app/ai/_components/ai-workspace", () => ({ AiWorkspace: () => {
  const auth = useContext(AuthContext)
  return <div data-runtime="" data-user={auth?.user?.id ?? "none"} />
} }))
vi.mock("framer-motion", () => ({ LayoutGroup: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement, root: Root
beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_PLAYWRIGHT_E2E", "1")
  state.pathname = "/e2e/shots/ai"
  host = document.createElement("div"); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllEnvs() })
it("mounts exactly one captured runtime within fixture auth instead of the outer unauthenticated host", async () => {
  await act(async () => root.render(<><GravitreAIWorkspaceHost /><ShotAuthProvider><GravitreAIWorkspaceHost fixtureBoundary /></ShotAuthProvider></>))
  const runtimes = host.querySelectorAll('[data-runtime]')
  expect(runtimes).toHaveLength(1)
  expect(runtimes[0].getAttribute("data-user")).not.toBe("none")
})
it("preserves root-host mounting on ordinary product routes", async () => {
  state.pathname = "/home"
  await act(async () => root.render(<GravitreAIWorkspaceHost />))
  expect(host.querySelectorAll('[data-runtime]')).toHaveLength(1)
})
