"use client"

import {
  CheckCircle2,
  CircleAlert,
  Info,
  Loader2,
  TriangleAlert,
  X,
} from "lucide-react"
import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { cn } from "@/lib/utils"

/**
 * Gravitre / v0 toast surface:
 * Neutral card, soft elevation, Lucide icons — not pastel richColors fills.
 */
const Toaster = ({ className, toastOptions, ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()
  const callerClasses = toastOptions?.classNames

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className={cn("toaster group", className)}
      closeButton
      expand={false}
      visibleToasts={4}
      gap={10}
      offset={16}
      duration={4500}
      icons={{
        success: (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/20">
            <CheckCircle2 className="h-4 w-4" strokeWidth={2} aria-hidden />
          </span>
        ),
        error: (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive ring-1 ring-destructive/20">
            <CircleAlert className="h-4 w-4" strokeWidth={2} aria-hidden />
          </span>
        ),
        warning: (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_oklch,var(--warning)_14%,transparent)] text-[var(--warning)] ring-1 ring-[color-mix(in_oklch,var(--warning)_28%,transparent)]">
            <TriangleAlert className="h-4 w-4" strokeWidth={2} aria-hidden />
          </span>
        ),
        info: (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_oklch,var(--info)_12%,transparent)] text-[var(--info)] ring-1 ring-[color-mix(in_oklch,var(--info)_28%,transparent)]">
            <Info className="h-4 w-4" strokeWidth={2} aria-hidden />
          </span>
        ),
        loading: (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-muted-foreground ring-1 ring-border/70">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} aria-hidden />
          </span>
        ),
        close: <X className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />,
      }}
      toastOptions={{
        ...toastOptions,
        unstyled: true,
        classNames: {
          toast: cn(
            "group/toast pointer-events-auto relative flex w-[min(100vw-2rem,22.5rem)] items-start gap-3",
            "rounded-2xl border border-border/70 bg-card p-4 pr-10 text-card-foreground",
            "shadow-[var(--elevation-3),var(--highlight-edge)] backdrop-blur-sm",
            callerClasses?.toast,
          ),
          title: cn(
            "text-sm font-semibold tracking-tight text-foreground",
            callerClasses?.title,
          ),
          description: cn(
            "mt-0.5 line-clamp-3 text-[13px] leading-relaxed text-muted-foreground",
            callerClasses?.description,
          ),
          actionButton: cn(
            "mt-2 inline-flex h-8 shrink-0 items-center justify-center rounded-lg px-3",
            "bg-primary text-xs font-medium text-primary-foreground transition hover:opacity-90",
            callerClasses?.actionButton,
          ),
          cancelButton: cn(
            "mt-2 inline-flex h-8 shrink-0 items-center justify-center rounded-lg px-3",
            "border border-border/70 bg-secondary/60 text-xs font-medium text-foreground transition hover:bg-secondary",
            callerClasses?.cancelButton,
          ),
          closeButton: cn(
            "!absolute !right-2.5 !top-2.5 !left-auto !transform-none",
            "!flex !h-7 !w-7 !items-center !justify-center !rounded-lg !border-0",
            "!bg-transparent !text-muted-foreground/70",
            "transition hover:!bg-secondary hover:!text-foreground",
            callerClasses?.closeButton,
          ),
          success: cn("border-primary/25", callerClasses?.success),
          error: cn("border-destructive/25", callerClasses?.error),
          warning: cn(
            "border-[color-mix(in_oklch,var(--warning)_35%,var(--border))]",
            callerClasses?.warning,
          ),
          info: cn(
            "border-[color-mix(in_oklch,var(--info)_35%,var(--border))]",
            callerClasses?.info,
          ),
          loading: callerClasses?.loading,
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
