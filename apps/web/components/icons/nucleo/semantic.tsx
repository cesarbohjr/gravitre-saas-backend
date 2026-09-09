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
import { NavActivity } from "@/components/icons/nodus-nav/outline"
// Phase 4 (Gravitre AI Agent Workspace redesign, Part C1 icon-gap closure —
// see docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md).
// These 14 files were originally Nucleo-STYLE constructions (visual
// approximations, not licensed assets — disclosed as such in the Phase 4
// report). On 2026-09-09, Cesar provided direct local access to his paid
// Nucleo desktop-app library (C:\Users\Cesar\AppData\Roaming\Nucleo\icons,
// "Nucleo Sharp" family / group_id=4, 24px grid — confirmed as the exact
// family already used by every other file in this folder, e.g. the two-line
// XmarkOutline24 with strokeMiterlimit=10 + data-color="color-2" matches
// Sharp Essential icon id 1304 path-for-path). All 14 were re-sourced from
// that real, licensed library and are now genuine Nucleo assets. See each
// file's header comment for its specific source icon name. Two files
// (MinimizeOutline24, MicrophoneOutline24) combine a real Nucleo path with a
// small generic accent line (not a distinct Nucleo glyph) to preserve the
// original compound reading; disclosed in those files' comments.
import { ExpandOutline24 } from "./ExpandOutline24"
import { CollapseOutline24 } from "./CollapseOutline24"
import { MinimizeOutline24 } from "./MinimizeOutline24"
import { FullscreenOutline24 } from "./FullscreenOutline24"
import { MicrophoneOutline24 } from "./MicrophoneOutline24"
import { PaperclipOutline24 } from "./PaperclipOutline24"
import { SendOutline24 } from "./SendOutline24"
import { PlayOutline24 } from "./PlayOutline24"
import { CheckCircleOutline24 } from "./CheckCircleOutline24"
import { XCircleOutline24 } from "./XCircleOutline24"
import { SettingsOutline24 } from "./SettingsOutline24"
import { HistoryOutline24 } from "./HistoryOutline24"
import { NewChatOutline24 } from "./NewChatOutline24"
import { PanelToggleOutline24 } from "./PanelToggleOutline24"

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
/** Expand a window/panel outward (Float → Expanded) */
export const NucleoExpand = withSize(ExpandOutline24)
/** Collapse a window/panel inward (Fullscreen → Expanded) */
export const NucleoCollapse = withSize(CollapseOutline24)
/** Minimize / dock down to the Helper bubble */
export const NucleoMinimize = withSize(MinimizeOutline24)
/** Enter fullscreen (4-corner frame) */
export const NucleoFullscreen = withSize(FullscreenOutline24)
/** Voice input / microphone */
export const NucleoMic = withSize(MicrophoneOutline24)
/** Attach a file */
export const NucleoAttach = withSize(PaperclipOutline24)
/** Send a message */
export const NucleoSend = withSize(SendOutline24)
/** Run / execute an action */
export const NucleoRun = withSize(PlayOutline24)
/** Success / completed */
export const NucleoSuccess = withSize(CheckCircleOutline24)
/** Error / failed */
export const NucleoError = withSize(XCircleOutline24)
/** Settings / preferences */
export const NucleoSettings = withSize(SettingsOutline24)
/** History / past conversations */
export const NucleoHistory = withSize(HistoryOutline24)
/** Start a new chat/conversation */
export const NucleoNewChat = withSize(NewChatOutline24)
/** Toggle a side panel open/closed */
export const NucleoPanelToggle = withSize(PanelToggleOutline24)
/** Activity / execution log */
export const NucleoActivity = ({
  className,
  size = 24,
  width,
  height,
  ...props
}: IconProps) => {
  const dim = width ?? height ?? size
  return <NavActivity className={className} size={dim} {...props} />
}

export const SEMANTIC_NUCLEO = {
  agent: NucleoAgent,
  connector: NucleoConnector,
  intelligence: NucleoIntelligence,
  voice: NucleoVoice,
  approval: NucleoApproval,
  workflow: NucleoWorkflow,
  activity: NucleoActivity,
  arrowRight: NucleoArrowRight,
  menu: NucleoMenu,
  chevronDown: NucleoChevronDown,
  close: NucleoClose,
  bell: NucleoBell,
  command: NucleoCommand,
  search: NucleoSearch,
  expand: NucleoExpand,
  collapse: NucleoCollapse,
  minimize: NucleoMinimize,
  fullscreen: NucleoFullscreen,
  mic: NucleoMic,
  attach: NucleoAttach,
  send: NucleoSend,
  run: NucleoRun,
  success: NucleoSuccess,
  error: NucleoError,
  settings: NucleoSettings,
  history: NucleoHistory,
  newChat: NucleoNewChat,
  panelToggle: NucleoPanelToggle,
} as const
