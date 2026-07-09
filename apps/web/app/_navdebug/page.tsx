"use client"

// TEMPORARY DIAGNOSTIC PAGE — remove after root-causing soft-nav failure.
// Rendered inside AppShell to reproduce the authenticated app context.
// Uses BUTTONS calling the real App Router (useRouter from next/navigation),
// which bypasses the <a>-click hard-navigation interceptor so we can observe
// raw client-side soft navigation behavior.

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"

export default function NavDebugPage() {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()
  const [log, setLog] = useState<string[]>([])

  const append = (m: string) => {
    console.log("[v0] navdebug:", m)
    setLog((prev) => [...prev, `${new Date().toISOString().slice(11, 23)} ${m}`])
  }

  const testPush = (href: string) => {
    append(`before push -> ${href} | pathname=${window.location.pathname}`)
    try {
      const ret = router.push(href)
      append(`router.push returned: ${Object.prototype.toString.call(ret)}`)
    } catch (e) {
      append(`router.push THREW: ${String(e)}`)
    }
    setTimeout(() => {
      append(`+800ms pathname=${window.location.pathname} isPending=${isPending}`)
    }, 800)
  }

  const testTransitionPush = (href: string) => {
    append(`startTransition push -> ${href}`)
    startTransition(() => {
      router.push(href)
      append(`inside transition, dispatched push -> ${href}`)
    })
  }

  return (
    <AppShell>
      <div className="p-8 space-y-4">
        <h1 className="text-xl font-semibold">Soft-nav diagnostic</h1>
        <p className="text-sm text-muted-foreground">
          isPending: <span className="font-mono">{String(isPending)}</span>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => testPush("/home")}>router.push(/home)</Button>
          <Button onClick={() => testPush("/agents")}>router.push(/agents)</Button>
          <Button onClick={() => testPush("/runs")}>router.push(/runs)</Button>
          <Button variant="outline" onClick={() => testTransitionPush("/agents")}>
            startTransition push(/agents)
          </Button>
          <Button variant="outline" onClick={() => router.refresh()}>
            router.refresh()
          </Button>
        </div>
        <pre className="mt-4 max-h-96 overflow-auto rounded bg-muted p-3 text-xs">
          {log.join("\n") || "(no events yet)"}
        </pre>
      </div>
    </AppShell>
  )
}
