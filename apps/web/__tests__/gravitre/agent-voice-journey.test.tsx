// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { beforeEach, afterEach, expect, it, vi } from "vitest"
import { AgentVoiceAssignment } from "@/components/gravitre/agent-voice-assignment"
const state = vi.hoisted(() => ({
  fetch: vi.fn(),
  play: vi.fn(),
  pause: vi.fn(),
  revoke: vi.fn(),
  audio: null as null | { onended: (() => void) | null },
}))
vi.mock("@/lib/fetcher", () => ({ apiFetch: state.fetch }))
vi.mock("@/components/gravitre/assistant/voice-presentation", () => ({
  GravitreWave: () => <span>Playing</span>,
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
;(
  globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true
let root: Root, container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks()
  state.play.mockResolvedValue(undefined)
  state.fetch.mockImplementation(async (path: string) => ({
    ok: true,
    json: async () =>
      path === "/api/voice/library"
        ? { voices: [{ voice_id: "voice", key: "voice", name: "Calm" }] }
        : path === "/api/voice/design"
          ? {
              previews: [
                { generated_voice_id: "generated", audio_base_64: "audio" },
              ],
            }
          : { voice_id: "saved" },
    blob: async () => new Blob(["audio"]),
  }))
  vi.stubGlobal(
    "Audio",
    class {
      onended = null
      onerror = null
      play = state.play
      pause = state.pause
      constructor() {
        state.audio = this
      }
    },
  )
  const OriginalURL = URL
  vi.stubGlobal(
    "URL",
    class extends OriginalURL {
      static createObjectURL() {
        return "blob:preview"
      }
      static revokeObjectURL = state.revoke
    },
  )
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})
const click = (text: string) =>
  act(() =>
    [...container.querySelectorAll<HTMLButtonElement>("button")]
      .find((b) => b.textContent?.trim() === text)!
      .click(),
  )
const render = async () => {
  const changed = vi.fn()
  await act(async () =>
    root.render(<AgentVoiceAssignment value={{}} onChange={changed} />),
  )
  return changed
}
const describe = () =>
  act(() => {
    const input = container.querySelector("textarea")!
    Object.getOwnPropertyDescriptor(
      HTMLTextAreaElement.prototype,
      "value",
    )!.set!.call(input, "A calm clear voice")
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
it("shows library errors and allows a real retry", async () => {
  state.fetch.mockRejectedValueOnce(new Error("Offline"))
  await render()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "Offline",
  )
  expect(container.textContent).not.toContain("No library voices returned")
  await act(async () => click("Retry voice library"))
  expect(container.textContent).toContain("Calm")
})
it("handles rejected voice previews without an unhandled promise", async () => {
  await render()
  state.fetch.mockRejectedValueOnce(new Error("Preview offline"))
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Preview Calm"]')!
      .click(),
  )
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "Preview offline",
  )
  expect(
    container.querySelector<HTMLButtonElement>('[aria-label="Preview Calm"]')
      ?.disabled,
  ).toBe(false)
})
it("keeps preview pending for audio playback and cleans it up on unmount", async () => {
  await render()
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Preview Calm"]')!
      .click(),
  )
  expect(
    container.querySelector<HTMLButtonElement>('[aria-label="Preview Calm"]')
      ?.disabled,
  ).toBe(true)
  act(() => root.render(null))
  expect(state.pause).toHaveBeenCalled()
  expect(state.revoke).toHaveBeenCalledWith("blob:preview")
})
it("retains generated takes after a failed generation retry", async () => {
  await render()
  click("Design a voice")
  describe()
  await act(async () => click("Generate previews"))
  expect(container.textContent).toContain("Take 1")
  state.fetch.mockRejectedValueOnce(new Error("Design offline"))
  await act(async () => click("Generate previews"))
  expect(container.textContent).toContain("Take 1")
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "Design offline",
  )
})
it("prevents duplicate custom saves and only changes assignment after the API returns an ID", async () => {
  const changed = await render()
  click("Design a voice")
  describe()
  await act(async () => click("Generate previews"))
  let finish!: (response: unknown) => void
  state.fetch.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  click("Save to library")
  expect(changed).not.toHaveBeenCalled()
  expect(
    [...container.querySelectorAll<HTMLButtonElement>("button")].find(
      (b) => b.textContent === "Saving…",
    )?.disabled,
  ).toBe(true)
  await act(async () =>
    finish({ ok: true, json: async () => ({ voice_id: "saved" }) }),
  )
  expect(changed).toHaveBeenCalledWith(
    expect.objectContaining({
      voice_id: "saved",
      voice_source: "custom_voice_v3",
    }),
  )
  expect(
    state.fetch.mock.calls.filter(
      ([path]) => path === "/api/voice/design/save",
    ),
  ).toHaveLength(1)
})

it("does not start playback after the user stops a pending preview", async () => {
  await render()
  let finish!: (response: unknown) => void
  state.fetch.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  act(() =>
    container
      .querySelector<HTMLButtonElement>('[aria-label="Preview Calm"]')!
      .click(),
  )
  click("Stop preview")
  await act(async () =>
    finish({ ok: true, blob: async () => new Blob(["audio"]) }),
  )
  expect(state.play).not.toHaveBeenCalled()
  expect(container.textContent).not.toContain("Playing")
})
