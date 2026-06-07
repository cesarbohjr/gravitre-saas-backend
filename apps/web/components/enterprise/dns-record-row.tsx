"use client"

import { useState } from "react"
import { Check, Copy } from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface DnsRecordRowProps {
  label: string
  type: string
  host: string
  value: string
}

export function DnsRecordRow({ label, type, host, value }: DnsRecordRowProps) {
  const [copied, setCopied] = useState<string | null>(null)

  const copy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(field)
      toast.success("Copied to clipboard")
      setTimeout(() => setCopied(null), 2000)
    } catch {
      toast.error("Could not copy")
    }
  }

  return (
    <div className="rounded-lg border border-border bg-secondary/20 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <span className="rounded bg-background px-2 py-0.5 text-[10px] font-mono text-muted-foreground">{type}</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Host</p>
          <div className="mt-1 flex items-center gap-1">
            <code className="flex-1 truncate rounded bg-background px-2 py-1 text-xs">{host}</code>
            <Button type="button" size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => copy(host, `${label}-host`)}>
              {copied === `${label}-host` ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground/70">Value</p>
          <div className="mt-1 flex items-center gap-1">
            <code className="flex-1 truncate rounded bg-background px-2 py-1 text-xs">{value}</code>
            <Button type="button" size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => copy(value, `${label}-value`)}>
              {copied === `${label}-value` ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
