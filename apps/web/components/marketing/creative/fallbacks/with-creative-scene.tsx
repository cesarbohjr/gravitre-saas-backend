"use client"

import { type ComponentType } from "react"
import { CreativeErrorBoundary } from "../fallbacks/creative-error-boundary"

export function withCreativeScene<P extends object>(
  Scene: ComponentType<P>,
  scene: string,
): ComponentType<P> {
  function Wrapped(props: P) {
    return (
      <CreativeErrorBoundary scene={scene}>
        <Scene {...props} />
      </CreativeErrorBoundary>
    )
  }
  Wrapped.displayName = `CreativeScene(${scene})`
  return Wrapped
}
