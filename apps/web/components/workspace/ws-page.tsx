import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import "@/components/workspace/workspace.css"

/** Scope wrapper for the Workspace redesign v1 pages (see workspace.css). */
export function WsPage({
  children,
  className,
  wide = true,
}: {
  children: ReactNode
  className?: string
  /** Wrap children in the 1360px page frame. */
  wide?: boolean
}) {
  return (
    <div className={cn("gv-ws", className)}>
      {wide ? <div className="gv-page">{children}</div> : children}
    </div>
  )
}
