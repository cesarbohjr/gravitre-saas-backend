// @vitest-environment jsdom
import React, { act, useState } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
let listeners: (() => void)[]
beforeEach(() => {
  Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 834 })
  listeners = []
  vi.stubGlobal("matchMedia", vi.fn(() => ({ addEventListener: (_: string, cb: () => void) => listeners.push(cb), removeEventListener() {} })))
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
})
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals() })
function Example() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState("Existing target")
  return <><button onClick={() => setOpen(true)}>Inspect</button><SelectionInspector open={open} onOpenChange={setOpen} title="Dataset" description="Review before use"><input aria-label="Target" value={value} onChange={e => setValue(e.target.value)} /></SelectionInspector></>
}
const mount = () => act(() => root.render(<Example />))
const open = () => act(() => { const button = container.querySelector("button")!; button.focus(); button.click() })
it("keeps inspection closed until selection and discloses tablet context in a named sheet", () => {
  mount(); expect(document.querySelector('[role="dialog"]')).toBeNull(); open()
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Dataset")
  expect(document.querySelector('[role="dialog"] input')?.getAttribute("value")).toBe("Existing target")
})
it("restores the selection control when the sheet closes", async () => {
  mount(); open()
  act(() => [...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find(b => b.textContent === "Close")!.click())
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(document.activeElement).toBe(container.querySelector("button"))
})
it("moves selected context into the desktop work area without losing the target", () => {
  mount(); open()
  act(() => { window.innerWidth = 1440; listeners.forEach(cb => cb()) })
  expect(document.querySelector('[role="dialog"]')).toBeNull()
  expect(container.querySelector('aside[aria-label="Dataset"] input')?.getAttribute("value")).toBe("Existing target")
})
