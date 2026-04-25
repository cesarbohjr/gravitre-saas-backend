"use client"

import { forwardRef, type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils"
import { Icon, type IconName, type IconSize } from "@/lib/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

type IconButtonSize = "sm" | "md" | "lg"
type IconButtonVariant = "ghost" | "outline" | "solid" | "subtle"

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: IconName
  label: string // Required for accessibility, shown in tooltip
  size?: IconButtonSize
  variant?: IconButtonVariant
  emphasis?: boolean
  showTooltip?: boolean
  tooltipSide?: "top" | "right" | "bottom" | "left"
}

const sizeConfig: Record<IconButtonSize, { button: string; icon: IconSize }> = {
  sm: { button: "h-7 w-7", icon: "sm" },
  md: { button: "h-8 w-8", icon: "md" },
  lg: { button: "h-9 w-9", icon: "lg" },
}

const variantStyles: Record<IconButtonVariant, string> = {
  ghost: "bg-transparent hover:bg-accent active:bg-accent/80 text-muted-foreground hover:text-foreground",
  outline: "bg-transparent border border-border hover:bg-accent hover:border-muted-foreground/50 active:bg-accent/80 text-muted-foreground hover:text-foreground",
  solid: "bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80",
  subtle: "bg-secondary/50 hover:bg-secondary active:bg-secondary/80 text-muted-foreground hover:text-foreground",
}

/**
 * Consistent icon button with proper hover, focus, and pressed states.
 * Always requires a label for accessibility (shown in tooltip).
 * 
 * Usage:
 * <IconButton icon="settings" label="Settings" />
 * <IconButton icon="delete" label="Delete item" variant="outline" />
 */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      label,
      size = "md",
      variant = "ghost",
      emphasis = false,
      showTooltip = true,
      tooltipSide = "top",
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const { button: buttonSize, icon: iconSize } = sizeConfig[size]

    const button = (
      <button
        ref={ref}
        type="button"
        disabled={disabled}
        aria-label={label}
        className={cn(
          "inline-flex items-center justify-center rounded-lg transition-all duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          "disabled:pointer-events-none disabled:opacity-50",
          buttonSize,
          variantStyles[variant],
          className
        )}
        {...props}
      >
        <Icon name={icon} size={iconSize} emphasis={emphasis} />
      </button>
    )

    if (!showTooltip) {
      return button
    }

    return (
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>{button}</TooltipTrigger>
          <TooltipContent side={tooltipSide} className="text-xs">
            {label}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }
)

IconButton.displayName = "IconButton"

/**
 * Group of icon buttons with consistent spacing
 */
export function IconButtonGroup({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {children}
    </div>
  )
}
