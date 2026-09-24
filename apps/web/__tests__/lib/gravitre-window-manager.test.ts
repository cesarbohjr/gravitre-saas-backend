import { describe, expect, it } from "vitest"
import {
  resolveContextualWindowDefault,
  resolvePreferredWindowMode,
  transitionWindowMode,
  writeWindowManagerPreference,
  readWindowManagerPreference,
  GRAVITRE_WM_PREFERENCE_STORAGE_KEY,
  type WindowManagerIdentity,
} from "@/lib/gravitre-window-manager"

function memoryStorage(seed: Record<string, string> = {}) {
  const map = new Map(Object.entries(seed))
  return {
    getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
    setItem: (k: string, v: string) => {
      map.set(k, v)
    },
  }
}

const identity: WindowManagerIdentity = {
  conversationId: "conv_1",
  taskId: "task_1",
  artifactId: "art_1",
  approvalId: "appr_1",
  voiceSessionId: null,
}

describe("window manager contextual default (G-STRUCT Option A)", () => {
  it("does not force docked as the universal default", () => {
    expect(
      resolveContextualWindowDefault({ pathname: "/dashboard", viewportWidth: 1280 }),
    ).toBe("floating")
    expect(resolveContextualWindowDefault({ pathname: "/ai", viewportWidth: 1280 })).toBe("expanded")
  })

  it("uses docked for expert workspaces only", () => {
    expect(
      resolveContextualWindowDefault({
        pathname: "/workflows/abc/builder",
        viewportWidth: 1440,
        expertWorkspace: true,
      }),
    ).toBe("docked")
  })

  it("prefers compact on narrow viewports", () => {
    expect(resolveContextualWindowDefault({ pathname: "/dashboard", viewportWidth: 390 })).toBe(
      "compact",
    )
  })

  it("lets remembered preference win over contextual default", () => {
    expect(
      resolvePreferredWindowMode({
        hints: { pathname: "/dashboard", viewportWidth: 1280 },
        preference: "docked",
      }),
    ).toBe("docked")
  })

  it("persists preference best-effort", () => {
    const storage = memoryStorage()
    writeWindowManagerPreference("expanded", storage)
    expect(storage.getItem(GRAVITRE_WM_PREFERENCE_STORAGE_KEY)).toBe("expanded")
    expect(readWindowManagerPreference(storage)).toBe("expanded")
  })
})

describe("window manager identity preservation", () => {
  it("keeps the same identity object across mode transitions", () => {
    const a = transitionWindowMode({
      from: "floating",
      to: "docked",
      identity,
      lastMeaningful: "floating",
    })
    expect(a.identity).toBe(identity)
    expect(a.identity.conversationId).toBe("conv_1")
    expect(a.mode).toBe("docked")

    const b = transitionWindowMode({
      from: "docked",
      to: "minimized",
      identity: a.identity,
      lastMeaningful: a.lastMeaningful,
    })
    expect(b.identity).toBe(identity)
    expect(b.mode).toBe("minimized")
    expect(b.lastMeaningful).toBe("docked")

    const c = transitionWindowMode({
      from: "minimized",
      to: "restored",
      identity: b.identity,
      lastMeaningful: b.lastMeaningful,
    })
    expect(c.identity).toBe(identity)
    expect(c.mode).toBe("docked")
  })
})
