// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, expect, it } from "vitest"
import { ConnectorsToaster } from "@/components/connectors/overlays/connectors-toaster"
import { removeConnectorsToast, toast } from "@/components/connectors/overlays/toast"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root | null = null
afterEach(() => {
  act(() => removeConnectorsToast())
  act(() => root?.unmount())
  root = null
  document.body.innerHTML = ""
})

it("uses the shared shell: a tone tile, with the system named in the eyebrow", () => {
  const host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  act(() => root!.render(<ConnectorsToaster />))
  act(() => {
    toast.error("Zendesk sign-in expired", { vendor: "zendesk", description: "Reconnect to resume." })
  })
  const card = host.querySelector(".cno-toast") as HTMLElement
  expect(card.dataset.tone).toBe("error")
  const tile = card.querySelector(".cno-tile") as HTMLElement
  expect(tile.className).toBe("cno-tile")
  expect(tile.querySelector("svg")).not.toBeNull()
  expect(tile.querySelector("img")).toBeNull()
  expect(card.querySelector(".cno-eyebrow")?.textContent).toMatch(/^Zendesk/)
})
