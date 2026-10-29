"use client"

import type { ReactNode } from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog"
import { X } from "lucide-react"
import { vendorLook } from "@/components/connectors/redesign/vendor-look"
import "./overlays.css"

/**
 * A form dialog in the Connectors shell ("Configure Zendesk" in the design):
 * the system's mono tile, a title with one line of context, a close button,
 * labelled fields, then a footer with Cancel and the primary action. 440px on
 * a 48% ink scrim; a bottom sheet on phones.
 */
export function ConnectorsDialog({
  open,
  onOpenChange,
  vendor,
  title,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Shows that system's mono tile beside the title. */
  vendor?: string
  title: string
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  /** The add-connector flow needs more room than a settings form. */
  wide?: boolean
}) {
  const look = vendor ? vendorLook(vendor) : null
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="cno-scrim" />
        <DialogPrimitive.Content className={`cno-dialog${wide ? " wide" : ""}`}>
          <div className="cno-dialog-head">
            {look ? (
              <span className="cno-tile mono" style={{ background: look.bg, color: look.fg }} aria-hidden>
                {look.mono}
              </span>
            ) : null}
            <div className="cno-dialog-heading">
              <DialogPrimitive.Title className="cno-dialog-title">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="cno-dialog-desc">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close className="cno-x filled" aria-label="Close">
              <X size={14} strokeWidth={2.4} aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <div className="cno-dialog-body">{children}</div>
          {footer ? <div className="cno-dialog-foot">{footer}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

/**
 * The red "Remove HubSpot?" alert: a warning tile, what happens right away as
 * bullets, then whatever the caller adds (the type-the-name field) and a
 * footer. Escape and the scrim cancel; nothing closes it by accident.
 */
export function ConnectorsAlertDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  icon,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  children?: ReactNode
  footer: ReactNode
  icon: ReactNode
}) {
  return (
    <AlertDialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay className="cno-scrim" />
        <AlertDialogPrimitive.Content className="cno-dialog alert">
          <div className="cno-dialog-head">
            <span className="cno-tile danger" aria-hidden>
              {icon}
            </span>
            <div className="cno-dialog-heading">
              <AlertDialogPrimitive.Title className="cno-dialog-title sm">{title}</AlertDialogPrimitive.Title>
              {description ? (
                <AlertDialogPrimitive.Description className="cno-dialog-desc">{description}</AlertDialogPrimitive.Description>
              ) : (
                <AlertDialogPrimitive.Description className="sr-only">{title}</AlertDialogPrimitive.Description>
              )}
            </div>
          </div>
          {children ? <div className="cno-dialog-body">{children}</div> : null}
          <div className="cno-dialog-foot">{footer}</div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  )
}

/** Bulleted consequences in the remove dialog; `mute` is the grey "nothing changes" line. */
export function ConnectorsBullets({ items }: { items: Array<{ text: ReactNode; mute?: boolean }> }) {
  return (
    <ul className="cno-bullets">
      {items.map((item, index) => (
        <li key={index} data-mute={item.mute ? "true" : undefined}>
          <span aria-hidden />
          <span>{item.text}</span>
        </li>
      ))}
    </ul>
  )
}
