"use client"

import { useRef, type ReactNode } from "react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

/** Selection context sits beside desktop work and discloses over compact work. */
export function SelectionInspector({ open, onOpenChange, title, description, children, className, pending = false }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  children: ReactNode
  className?: string
  pending?: boolean
}) {
  const compact = useIsMobile(1024)
  const previousFocus = useRef<HTMLElement | null>(null)
  if (!compact) return open ? <aside aria-label={title} className={cn("min-w-0", className)}>{children}</aside> : null
  return (
    <Sheet open={open} onOpenChange={next => { if (!pending) onOpenChange(next) }}>
      <SheetContent
        closeDisabled={pending}
        onEscapeKeyDown={event => { if (pending) event.preventDefault() }}
        onInteractOutside={event => { if (pending) event.preventDefault() }}
        className="w-full overflow-y-auto pb-[env(safe-area-inset-bottom)] sm:max-w-[540px]"
        onOpenAutoFocus={() => { previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null }}
        onCloseAutoFocus={(event) => {
          if (previousFocus.current?.isConnected) { event.preventDefault(); previousFocus.current.focus() }
        }}
      >
        <SheetHeader className="pr-14">
          <SheetTitle className="font-sans">{title}</SheetTitle>
          <SheetDescription>{description}</SheetDescription>
        </SheetHeader>
        <div className="min-w-0 px-4 pb-6">{children}</div>
      </SheetContent>
    </Sheet>
  )
}
