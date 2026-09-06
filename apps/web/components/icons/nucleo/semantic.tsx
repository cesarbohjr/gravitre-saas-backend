/**
 * Semantic Nucleo icon map (UI 2.0 Phase 9).
 * Components are copied into this folder from Nucleo skills — never import from ~/.nucleo at runtime.
 *
 * Lucide-compatible: accept `className` (and optional absolute size via CSS).
 */
import type { ComponentType, SVGProps } from "react"
import { AiOutline24 } from "./AiOutline24"
import { PlugOutline24 } from "./PlugOutline24"
import { BrainNodesOutline24 } from "./BrainNodesOutline24"
import { WaveformLinesOutline24 } from "./WaveformLinesOutline24"
import { ShieldCheckOutline24 } from "./ShieldCheckOutline24"
import { BranchMergeOutline24 } from "./BranchMergeOutline24"
import { ArrowRightOutline24 } from "./ArrowRightOutline24"
import { MenuBarsOutline24 } from "./MenuBarsOutline24"
import { ChevronDownOutline24 } from "./ChevronDownOutline24"
import { XmarkOutline24 } from "./XmarkOutline24"
import { BellOutline24 } from "./BellOutline24"
import { CommandOutline24 } from "./CommandOutline24"
import { MagnifierOutline24 } from "./MagnifierOutline24"

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number | string
}

type NucleoSource = ComponentType<
  SVGProps<SVGSVGElement> & { strokeWidth?: number | string; corners?: "round" | "square" }
>

function withSize(Icon: NucleoSource) {
  return function NucleoSemanticIcon({ className, size = 24, width, height, ...props }: IconProps) {
    const dim = width ?? height ?? size
    return <Icon className={className} width={dim} height={dim} {...props} />
  }
}

/** Agent / AI teammate */
export const NucleoAgent = withSize(AiOutline24)
/** Connector / integration */
export const NucleoConnector = withSize(PlugOutline24)
/** GIBE / intelligence network */
export const NucleoIntelligence = withSize(BrainNodesOutline24)
/** Voice waveform */
export const NucleoVoice = withSize(WaveformLinesOutline24)
/** Approval / verified governance */
export const NucleoApproval = withSize(ShieldCheckOutline24)
/** Workflow / branch merge */
export const NucleoWorkflow = withSize(BranchMergeOutline24)
/** Arrow right / next */
export const NucleoArrowRight = withSize(ArrowRightOutline24)
/** Menu / hamburger bars */
export const NucleoMenu = withSize(MenuBarsOutline24)
/** Chevron down / expand */
export const NucleoChevronDown = withSize(ChevronDownOutline24)
/** Close / dismiss */
export const NucleoClose = withSize(XmarkOutline24)
/** Notifications */
export const NucleoBell = withSize(BellOutline24)
/** Keyboard command / shortcuts */
export const NucleoCommand = withSize(CommandOutline24)
/** Search / magnifier */
export const NucleoSearch = withSize(MagnifierOutline24)

export const SEMANTIC_NUCLEO = {
  agent: NucleoAgent,
  connector: NucleoConnector,
  intelligence: NucleoIntelligence,
  voice: NucleoVoice,
  approval: NucleoApproval,
  workflow: NucleoWorkflow,
  arrowRight: NucleoArrowRight,
  menu: NucleoMenu,
  chevronDown: NucleoChevronDown,
  close: NucleoClose,
  bell: NucleoBell,
  command: NucleoCommand,
  search: NucleoSearch,
} as const
