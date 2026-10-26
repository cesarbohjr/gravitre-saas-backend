'use client'

import * as React from 'react'
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog'

import { TriangleAlert } from 'lucide-react'

import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'
import { useAgentsSurface } from '@/components/agents/overlays/surface-context'
import { AGENTS_CARD, AGENTS_DESCRIPTION, AGENTS_FOOTER, AGENTS_SCRIM } from '@/components/ui/dialog'

/** "danger" marks a destructive confirm: red tile beside the title on the Agents surface. */
type AlertTone = 'danger' | undefined
const AlertToneContext = React.createContext<AlertTone>(undefined)

const AGENTS_BTN =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-[10px] border-0 px-4 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#19C37D] disabled:pointer-events-none disabled:opacity-50'
const AGENTS_BTN_DARK = 'bg-[#141513] text-white hover:bg-[#33342F] dark:bg-[#ededE8] dark:text-[#111211] dark:hover:bg-white'
const AGENTS_BTN_DANGER = 'bg-[#A3333D] text-white hover:bg-[#8C2A33]'
const AGENTS_BTN_GHOST = 'bg-[#EFEFEA] text-[#141513] hover:bg-[#E4E4DF] dark:bg-[#262825] dark:text-[#ededE8] dark:hover:bg-[#2f312d]'
const DESTRUCTIVE_CLASS = /destructive|danger|bg-red-|bg-rose-/

function AlertDialog({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Root>) {
  return <AlertDialogPrimitive.Root data-slot="alert-dialog" {...props} />
}

function AlertDialogTrigger({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Trigger>) {
  return (
    <AlertDialogPrimitive.Trigger data-slot="alert-dialog-trigger" {...props} />
  )
}

function AlertDialogPortal({
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Portal>) {
  return (
    <AlertDialogPrimitive.Portal data-slot="alert-dialog-portal" {...props} />
  )
}

function AlertDialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Overlay>) {
  const agents = useAgentsSurface()
  return (
    <AlertDialogPrimitive.Overlay
      data-slot="alert-dialog-overlay"
      className={cn(
        agents ? AGENTS_SCRIM : 'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 motion-reduce:animate-none fixed inset-0 z-50 bg-[color:var(--overlay)] backdrop-blur-[2px]',
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogContent({
  className,
  tone,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Content> & { tone?: AlertTone }) {
  const agents = useAgentsSurface()
  return (
    <AlertToneContext.Provider value={tone}>
      <AlertDialogPortal>
        <AlertDialogOverlay />
        <AlertDialogPrimitive.Content
          data-slot="alert-dialog-content"
          data-tone={tone}
          className={cn(
            agents ? cn(AGENTS_CARD, 'ag-alert gap-3') : 'bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-[var(--np-radius-lg)] border border-divide p-6 shadow-[var(--np-shadow)] duration-200 motion-reduce:animate-none motion-reduce:transition-none sm:max-w-lg',
            className,
          )}
          {...props}
        />
      </AlertDialogPortal>
    </AlertToneContext.Provider>
  )
}

function AlertDialogHeader({
  className,
  children,
  ...props
}: React.ComponentProps<'div'>) {
  const agents = useAgentsSurface()
  const tone = React.useContext(AlertToneContext)
  if (agents && tone === 'danger') {
    return (
      <div data-slot="alert-dialog-header" className={cn('flex items-start gap-3.5 text-left', className)} {...props}>
        <span className="grid size-10 flex-none place-items-center rounded-[10px] bg-[#F8E4E6] text-[#A3333D] dark:bg-[#3a1a1d] dark:text-[#f2a7ae]">
          <TriangleAlert size={18} strokeWidth={2} aria-hidden />
        </span>
        <div className="flex min-w-0 flex-col gap-1.5">{children}</div>
      </div>
    )
  }
  return (
    <div
      data-slot="alert-dialog-header"
      className={cn(agents ? 'flex flex-col gap-1.5 text-left' : 'flex flex-col gap-2 text-center sm:text-left', className)}
      {...props}
    >
      {children}
    </div>
  )
}

function AlertDialogFooter({
  className,
  ...props
}: React.ComponentProps<'div'>) {
  const agents = useAgentsSurface()
  return (
    <div
      data-slot="alert-dialog-footer"
      className={cn(
        agents ? cn(AGENTS_FOOTER, 'plain') : 'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end',
        className,
      )}
      {...props}
    />
  )
}

function AlertDialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Title>) {
  const agents = useAgentsSurface()
  return (
    <AlertDialogPrimitive.Title
      data-slot="alert-dialog-title"
      className={cn(agents ? 'break-words text-[17px] leading-snug font-semibold' : 'text-lg font-semibold', className)}
      {...props}
    />
  )
}

function AlertDialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Description>) {
  const agents = useAgentsSurface()
  return (
    <AlertDialogPrimitive.Description
      data-slot="alert-dialog-description"
      className={cn(agents ? AGENTS_DESCRIPTION : 'text-muted-foreground text-sm', className)}
      {...props}
    />
  )
}

function AlertDialogAction({
  className,
  tone,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Action> & { tone?: AlertTone }) {
  const agents = useAgentsSurface()
  const dialogTone = React.useContext(AlertToneContext)
  if (agents) {
    // A caller's destructive styling becomes the Agents danger button; other colours give way to the shell.
    const danger = tone === 'danger' || dialogTone === 'danger' || DESTRUCTIVE_CLASS.test(className ?? '')
    return (
      <AlertDialogPrimitive.Action
        className={cn(AGENTS_BTN, danger ? AGENTS_BTN_DANGER : AGENTS_BTN_DARK)}
        {...props}
      />
    )
  }
  return (
    <AlertDialogPrimitive.Action
      className={cn(buttonVariants(), className)}
      {...props}
    />
  )
}

function AlertDialogCancel({
  className,
  ...props
}: React.ComponentProps<typeof AlertDialogPrimitive.Cancel>) {
  const agents = useAgentsSurface()
  return (
    <AlertDialogPrimitive.Cancel
      className={agents ? cn(AGENTS_BTN, AGENTS_BTN_GHOST) : cn(buttonVariants({ variant: 'outline' }), className)}
      {...props}
    />
  )
}

export {
  AlertDialog,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
}
