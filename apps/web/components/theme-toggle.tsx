"use client"

import { Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TOUCH_ICON_BUTTON } from "@/lib/design-system"

/**
 * Light-first only (Nodus full-match Gate 0). Dark / system themes are disabled.
 * Kept as a stable import so shell call sites do not break.
 */
export function ThemeToggle() {
  return (
    <Button
      variant="ghost"
      size="icon"
      className={TOUCH_ICON_BUTTON}
      disabled
      title="Light theme (dark mode disabled)"
      aria-label="Light theme"
    >
      <Sun className="h-4 w-4" />
    </Button>
  )
}
