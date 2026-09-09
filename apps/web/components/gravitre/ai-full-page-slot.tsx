"use client"

/**
 * Phase 5 — full-page mount target for AiWorkspace when the float flag is on.
 *
 * AppProviders mounts one AiWorkspace host above every AppShell. Full-page
 * chrome must still paint inside `/ai`'s AppShell content area. This slot
 * lets AiWorkspace portal its full-page layout into the page while keeping
 * useChat / voice / approvals in the root-mounted instance.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"

type AiFullPageSlotContextValue = {
  slotElement: HTMLElement | null
  setSlotElement: (el: HTMLElement | null) => void
}

const AiFullPageSlotContext = createContext<AiFullPageSlotContextValue | null>(null)

export function AiFullPageSlotProvider({ children }: { children: ReactNode }) {
  const [slotElement, setSlotElementState] = useState<HTMLElement | null>(null)
  const setSlotElement = useCallback((el: HTMLElement | null) => {
    setSlotElementState(el)
  }, [])
  const value = useMemo(
    () => ({ slotElement, setSlotElement }),
    [slotElement, setSlotElement],
  )
  return (
    <AiFullPageSlotContext.Provider value={value}>{children}</AiFullPageSlotContext.Provider>
  )
}

export function useAiFullPageSlot(): AiFullPageSlotContextValue {
  const ctx = useContext(AiFullPageSlotContext)
  if (!ctx) {
    return {
      slotElement: null,
      setSlotElement: () => {},
    }
  }
  return ctx
}

/** Registers a DOM node as the full-page AiWorkspace portal target on `/ai`. */
export function AiWorkspaceFullPageSlot() {
  const ref = useRef<HTMLDivElement | null>(null)
  const { setSlotElement } = useAiFullPageSlot()

  useEffect(() => {
    setSlotElement(ref.current)
    return () => setSlotElement(null)
  }, [setSlotElement])

  return <div ref={ref as RefObject<HTMLDivElement>} className="flex min-h-0 flex-1 flex-col" data-gravitre-ai-full-page-slot="" />
}
