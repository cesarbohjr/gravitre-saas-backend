"use client"

import { useEffect, useId, useRef, useState } from "react"
import { CheckCircle2, Loader2, Tag, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  forgetPromoCode,
  normalizePromoCode,
  rememberPromoCode,
  type PromoValidation,
} from "@/lib/promotions"
import { validatePromoCode } from "@/lib/promotions-api"

export type AppliedPromo = { code: string; validation: PromoValidation }

type PromoCodeFieldProps = {
  /** Plan the code is checked against (restricted codes depend on it). */
  plan: string | null
  /** Code to start with, e.g. from ?promo= or a remembered signup code. */
  initialCode?: string | null
  /** Called with the applied (valid) code, or null when cleared / invalid. */
  onApplied: (applied: AppliedPromo | null) => void
  /** When set, the field is replaced by this note (e.g. a founder offer applies). */
  blockedReason?: string | null
  className?: string
  tone?: "app" | "marketing"
}

/**
 * Collapsible "Have a promo code?" field with live validation. Stripe
 * re-validates at checkout; this only previews the discount.
 */
export function PromoCodeField({ plan, initialCode, onApplied, blockedReason, className, tone = "app" }: PromoCodeFieldProps) {
  const inputId = useId()
  const [open, setOpen] = useState(Boolean(normalizePromoCode(initialCode)))
  const [draft, setDraft] = useState(normalizePromoCode(initialCode) ?? "")
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<PromoValidation | null>(null)
  const requestRef = useRef(0)
  const onAppliedRef = useRef(onApplied)
  onAppliedRef.current = onApplied

  useEffect(() => {
    const code = normalizePromoCode(draft)
    if (!code || blockedReason) {
      setResult(null)
      setChecking(false)
      onAppliedRef.current(null)
      return
    }
    const request = ++requestRef.current
    setChecking(true)
    const timer = window.setTimeout(() => {
      void validatePromoCode(code, plan).then((validation) => {
        if (request !== requestRef.current) return
        setChecking(false)
        setResult(validation)
        if (validation.valid) {
          rememberPromoCode(code)
          onAppliedRef.current({ code, validation })
        } else {
          onAppliedRef.current(null)
        }
      })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [draft, plan, blockedReason])

  if (blockedReason) {
    return (
      <p className={cn("flex items-start gap-2 text-xs text-muted-foreground", className)} data-testid="promo-code-blocked">
        <Tag className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span>{blockedReason}</span>
      </p>
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex items-center gap-1.5 text-xs font-medium underline-offset-4 hover:underline",
          tone === "marketing" ? "text-gray-600" : "text-muted-foreground hover:text-foreground",
          className,
        )}
        data-testid="promo-code-toggle"
      >
        <Tag className="h-3.5 w-3.5" aria-hidden />
        Have a promo code?
      </button>
    )
  }

  const clear = () => {
    setDraft("")
    setResult(null)
    forgetPromoCode()
    onAppliedRef.current(null)
  }

  return (
    <div className={cn("space-y-1.5", className)} data-testid="promo-code-field">
      <label htmlFor={inputId} className="block text-xs font-medium text-foreground">
        Promo code
      </label>
      <div className="flex items-center gap-2">
        <Input
          id={inputId}
          value={draft}
          onChange={(event) => setDraft(event.target.value.toUpperCase().replace(/\s+/g, ""))}
          placeholder="e.g. LAUNCH30"
          maxLength={40}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={result ? !result.valid : undefined}
          aria-describedby={`${inputId}-status`}
          className="h-9 font-mono text-sm"
        />
        {draft ? (
          <Button type="button" variant="ghost" size="sm" onClick={clear} aria-label="Remove promo code">
            <X className="h-4 w-4" />
          </Button>
        ) : null}
      </div>
      <p id={`${inputId}-status`} role="status" aria-live="polite" className="min-h-4 text-xs">
        {checking ? (
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> Checking code…
          </span>
        ) : result?.valid ? (
          <span className="inline-flex items-center gap-1.5 text-success" data-testid="promo-code-summary">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            {result.code ?? draft}: {result.summary}. Applied at checkout.
          </span>
        ) : result ? (
          <span className="text-destructive">{result.reason}</span>
        ) : null}
      </p>
    </div>
  )
}
