import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/**
 * Shape and hierarchy live here, not at call sites: the app renders 800+
 * buttons across ~175 files, so any convention that relies on each page opting
 * in drifts immediately.
 *
 * Hierarchy (master spec §12): `default` is the one primary action per screen
 * (graphite, inverts in dark), `brand` is reserved for emerald AI/commit moments,
 * `outline`/`secondary` are secondary, `ghost`/`link` are tertiary toolbar and
 * inline actions. Shape is a sharp 8px control radius (RADIUS.control), not a pill.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[var(--np-radius-md)] text-[13px] font-medium leading-none transition-[background-color,color,box-shadow,border-color] duration-150 cursor-pointer active:translate-y-px disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default:
          'bg-foreground text-background shadow-[inset_0_1px_0_0_rgb(255_255_255/0.12)] hover:bg-foreground/85',
        brand:
          'bg-primary text-primary-foreground hover:bg-[color:var(--g-brand-hover)] dark:hover:bg-primary/85',
        destructive:
          'bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/40',
        outline:
          'border border-[color:var(--g-border-default)] bg-background text-foreground hover:border-[color:var(--g-border-strong)] hover:bg-[color:var(--g-surface-2)]',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-[color:var(--g-surface-3)] dark:hover:bg-accent',
        ghost:
          'text-foreground/80 hover:bg-accent hover:text-accent-foreground',
        link: 'text-foreground underline decoration-[color:var(--g-border-strong)] underline-offset-4 hover:decoration-foreground',
      },
      size: {
        default: 'h-8 px-3 has-[>svg]:px-2.5',
        sm: 'h-7 gap-1 px-2.5 text-xs has-[>svg]:px-2',
        lg: 'h-9 px-4 text-sm has-[>svg]:px-3.5',
        icon: 'size-8',
        'icon-sm': 'size-7',
        'icon-lg': 'size-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
