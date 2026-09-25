import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/**
 * Badges are quiet 4px tags (RADIUS.tag), not pills. Soft colored fills are
 * reserved for important status (`status` / `warning` / `destructive`); meta
 * labels carry no border so rows don't fill up with outlined capsules.
 */
const badgeVariants = cva(
  'inline-flex h-5 items-center justify-center rounded-[4px] border border-transparent px-1.5 text-[11px] font-medium leading-none w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:ring-2 focus-visible:ring-ring aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive transition-[color,box-shadow] overflow-hidden',
  {
    variants: {
      variant: {
        /** Quiet default — category / meta labels */
        default:
          'bg-[color:var(--g-surface-3)] text-[color:var(--g-text-secondary)] [a&]:hover:bg-accent',
        secondary:
          'bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)] [a&]:hover:bg-[color:var(--g-surface-3)]',
        /** Hairline outline for counts and optional labels */
        outline:
          'border-[color:var(--g-border-default)] bg-transparent text-[color:var(--g-text-muted)] [a&]:hover:bg-[color:var(--g-surface-2)] [a&]:hover:text-[color:var(--g-text-primary)]',
        /** Important status only */
        status:
          'border-transparent bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]',
        warning:
          'border-transparent bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]',
        destructive:
          'border-transparent bg-destructive/10 text-destructive [a&]:hover:bg-destructive/10 focus-visible:ring-destructive/20',
        neutral:
          'border-transparent bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<'span'> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'span'

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
