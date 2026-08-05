import { Suspense } from "react"

import BuilderPage from "@/app/workflows/[id]/builder/page"

import { ShotAuthProvider } from "../shot-auth"

/**
 * The orchestration builder canvas, for marketing capture.
 *
 * Kept out of the `SHOT_SURFACES` map in shot-view.tsx: every entry there is
 * rendered as `<Surface />` with no props, but the builder is a client component
 * that reads `params` via `use()`. It needs a real promise passed in, so it gets
 * its own route instead of widening that map's type.
 *
 * The id is deliberately NOT a uuid. `loadBuilderGraph` gates on
 * `isPersistableWorkflowId` (a uuid test) and returns null for anything else,
 * which leaves the canvas on its `initialNodes` seed — a populated
 * Salesforce -> validator -> enrich -> approval pipeline. That keeps the shot
 * free of any dependency on database state.
 *
 * Suspense wraps it because the builder calls `useSearchParams`, which otherwise
 * opts the whole route into client-side bailout during prerender.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <BuilderPage params={Promise.resolve({ id: "shot-demo-builder" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
