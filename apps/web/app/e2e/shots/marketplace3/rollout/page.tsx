"use client"
import { SWRConfig, unstable_serialize } from "swr"
import { Marketplace3Rollout } from "@/components/marketplace/marketplace3-rollout"
import fixtures from "../fixtures.json"

const packs = Object.values(fixtures).map(w => ({ slug: w.asset.slug, title: w.asset.title, department: w.asset.slug, deployed: true, status: "draft", certificationLevel: "governed", storedCertificationLevel: "production_verified", fixturePassed: true, playCount: w.contract.plays.length, agentCount: w.contract.agents.length, kpiCount: w.contract.outcome.kpis.length, requiredSystems: w.contract.providers, runtimeEvidenceProviders: [], measuredOutcomeCount: 0, publishReady: false, nextGate: "live_production_runtime_evidence", blockingFindingCodes: [] }))
const fallback = {
  "marketplace3-live-readiness": { source: "fixture", packCount: 8, deployedPackCount: 8, governedCount: 8, productionVerifiedCount: 0, outcomeVerifiedCount: 0, packs },
  "marketplace3-pilot-organizations": { organizations: [{ id: "00000000-0000-0000-0000-000000000001", name: "Screenshot tenant" }] },
  ...Object.fromEntries(Object.values(fixtures).map(w => [unstable_serialize(["marketplace3-blueprint", w.asset.slug]), w])),
}
export default function RolloutShot() {
  return <SWRConfig value={{ fallback, revalidateOnMount: false, revalidateOnFocus: false, revalidateOnReconnect: false }}><main className="mx-auto max-w-5xl p-4 sm:p-6"><p className="mb-5 text-sm text-muted-foreground">Screenshot fixture · no tenant data or live results</p><Marketplace3Rollout /></main></SWRConfig>
}
