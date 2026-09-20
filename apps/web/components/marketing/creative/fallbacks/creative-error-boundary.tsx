"use client"

import { Component, type ErrorInfo, type ReactNode } from "react"
import { NucleoError } from "@/components/icons/nucleo/semantic"

export function CreativeSceneFallback({ scene }: { scene?: string }) {
  return (
    <div
      className="mx-auto w-full max-w-3xl rounded-2xl border border-divide bg-white p-5 text-center"
      data-testid="creative-scene-fallback"
      data-creative-fallback={scene ?? "unknown"}
      role="status"
    >
      <NucleoError className="mx-auto h-5 w-5 text-[color:var(--g-text-muted)]" aria-hidden />
      <p className="mt-2 text-sm font-medium text-[color:var(--g-text-secondary)]">
        This illustration could not load.
      </p>
      <p className="mt-1 text-[11px] text-[color:var(--g-text-muted)]">
        The rest of the page still works. Refresh to try again.
      </p>
    </div>
  )
}

type Props = { children: ReactNode; scene: string }
type State = { error: Error | null }

/**
 * Isolates creative scene crashes so marketing chrome / CTAs stay usable.
 */
export class CreativeErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (process.env.NODE_ENV !== "production") {
      console.error(`[creative:${this.props.scene}]`, error, info.componentStack)
    }
  }

  render() {
    if (this.state.error) {
      return <CreativeSceneFallback scene={this.props.scene} />
    }
    return this.props.children
  }
}
