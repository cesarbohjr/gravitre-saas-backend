export { CREATIVE_BRAND, CREATIVE_TOKENS, type CreativeQuality } from "./core/tokens"
export {
  resolveCreativeQuality,
  creativeDprCap,
  shouldRunCreativeAnimation,
  snapshotCreativePerformance,
  type CreativePerformanceSnapshot,
} from "./core/performance-manager"
export {
  topologyForCoreState,
  topologyEdgeCount,
  type TopologyLayout,
} from "./primitives/relational-topology"
export { GravitreAgentNode } from "./primitives/agent-node"
export { GravitreEvidenceMark } from "./primitives/evidence-mark"
export { CreativeErrorBoundary, CreativeSceneFallback } from "./fallbacks/creative-error-boundary"
export { withCreativeScene } from "./fallbacks/with-creative-scene"

import { AgentOrchestrationField as AgentOrchestrationFieldInner } from "./scenes/agent-orchestration/orchestration-field"
import { EntityConvergenceField as EntityConvergenceFieldInner } from "./scenes/knowledge-fabric/entity-convergence-field"
import { ConnectorFabricField as ConnectorFabricFieldInner } from "./scenes/connector-fabric/connector-fabric-field"
import { GovernedExecutionField as GovernedExecutionFieldInner } from "./scenes/governed-execution/governed-execution-field"
import { withCreativeScene as wrapCreativeScene } from "./fallbacks/with-creative-scene"

export const AgentOrchestrationField = wrapCreativeScene(AgentOrchestrationFieldInner, "orchestration")
export const EntityConvergenceField = wrapCreativeScene(EntityConvergenceFieldInner, "knowledge-fabric")
export const ConnectorFabricField = wrapCreativeScene(ConnectorFabricFieldInner, "connector-fabric")
export const GovernedExecutionField = wrapCreativeScene(GovernedExecutionFieldInner, "governed-execution")
