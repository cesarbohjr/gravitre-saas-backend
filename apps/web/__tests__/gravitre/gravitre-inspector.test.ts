// @vitest-environment jsdom
/**
 * Slice 1 — shared inspector: dialog semantics, Escape closes, focus returns to
 * the opener, and every kind renders its label. Props only.
 */
import { act, createElement, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  GravitreInspector,
  GravitreInspectorFields,
  GRAVITRE_INSPECTOR_KINDS,
  GRAVITRE_INSPECTOR_KIND_LABEL,
  type GravitreInspectorKind,
} from "@/components/gravitre/inspector"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let container: HTMLDivElement
let root: Root | null = null

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  if (root) {
    act(() => root!.unmount())
    root = null
  }
  container.remove()
})

function Harness({ kind }: { kind: GravitreInspectorKind }) {
  const [open, setOpen] = useState(false)
  return createElement(
    "div",
    null,
    createElement("button", { type: "button", id: "opener", onClick: () => setOpen(true) }, "Open"),
    createElement(
      GravitreInspector,
      { open, onOpenChange: setOpen, kind, title: "Acme renewal" },
      createElement(GravitreInspectorFields, { fields: [{ label: "Owner", value: "Operator" }] }),
    ),
  )
}

async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}

describe("GravitreInspector", () => {
  it("opens as a labelled dialog, closes on Escape, and returns focus to the opener", async () => {
    root = createRoot(container)
    act(() => root!.render(createElement(Harness, { kind: "evidence" })))
    const opener = container.querySelector<HTMLButtonElement>("#opener")!
    opener.focus()
    act(() => opener.click())
    await flush()

    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog!.getAttribute("data-gravitre-inspector")).toBe("evidence")
    expect(dialog!.getAttribute("aria-labelledby")).toBeTruthy()
    expect(dialog!.textContent).toContain("Evidence")
    expect(dialog!.textContent).toContain("Acme renewal")
    expect(dialog!.contains(document.activeElement)).toBe(true)

    act(() => {
      document.activeElement!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
    })
    await flush()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it("has a label for every kind", () => {
    for (const kind of GRAVITRE_INSPECTOR_KINDS) {
      expect(GRAVITRE_INSPECTOR_KIND_LABEL[kind]).toBeTruthy()
    }
  })
})
