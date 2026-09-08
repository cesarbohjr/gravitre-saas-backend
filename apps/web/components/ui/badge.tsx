import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/**
 * Badges are mostly quiet labels. Soft colored fills are reserved for
 * important status (`status` / `warning` / `destructive`) — not every tag.
 * Shape stays `rounded-full` (RADIUS.control).
 */
const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-full border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive transition-[color,box-shadow] overflow-hidden',
  {
    variants: {
      variant: {
        /** Quiet default — category / meta labels */
        default:
          'border-divide bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)] [a&]:hover:bg-[color:var(--g-surface-3)]',
        secondary:
          'border-transparent bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)] [a&]:hover:bg-[color:var(--g-surface-3)]',
        /** True outline — no soft purple fill */
        outline:
          'border-divide bg-transparent text-[color:var(--g-text-muted)] [a&]:hover:bg-[color:var(--g-surface-2)] [a&]:hover:text-[color:var(--g-text-primary)]',
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
