"use client"

import type { ButtonHTMLAttributes, ReactNode } from "react"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

/** Opens the persistent docked/floating assistant instead of navigating to /ai. */
export function OpenGravitreAIButton({
  children,
  className,
  prompt,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  prompt?: string
}) {
  const { summonWorkspace } = useGravitreAIWorkspace()

  return (
    <button
      type="button"
      className={className}
      {...props}
      onClick={(event) => {
        props.onClick?.(event)
        if (event.defaultPrevented) return
        summonWorkspace({ composerText: prompt?.trim() || undefined })
      }}
    >
      {children}
    </button>
  )
}
