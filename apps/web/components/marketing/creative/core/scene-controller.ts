/**
 * CES 2.0 — SceneController foundation.
 *
 * Separates NARRATIVE PROGRESSION from USER SELECTION from PRODUCT DATA.
 * Selecting an object must not reset beat index. Viewport changes must not wipe step.
 *
 * Audit note: existing marketing scenes use independent setTimeout phase loops +
 * useCreativePerformance for visibility/reduced-motion. This controller is the
 * shared progression model for visitor-controlled / stepped prototypes — not a
 * second graphics runtime.
 */

export type PlaybackMode = "autoplay" | "paused" | "stepped"

export type SceneControllerSnapshot<TBeat extends string> = {
  beats: readonly TBeat[]
  beatIndex: number
  beat: TBeat
  mode: PlaybackMode
  /** Independent of narrative progression */
  selectedObjectId: string | null
  inspectOpen: boolean
}

export type SceneControllerAction<TBeat extends string> =
  | { type: "pause" }
  | { type: "resume" }
  | { type: "setMode"; mode: PlaybackMode }
  | { type: "stepForward" }
  | { type: "stepBack" }
  | { type: "replay" }
  | { type: "reset" }
  | { type: "selectObject"; id: string | null }
  | { type: "inspect"; open: boolean }
  | { type: "setBeatIndex"; index: number }
  | { type: "setBeat"; beat: TBeat }

export function createSceneControllerState<TBeat extends string>(
  beats: readonly TBeat[],
  opts?: { mode?: PlaybackMode; beatIndex?: number },
): SceneControllerSnapshot<TBeat> {
  const beatIndex = Math.min(Math.max(opts?.beatIndex ?? 0, 0), Math.max(beats.length - 1, 0))
  return {
    beats,
    beatIndex,
    beat: beats[beatIndex] ?? beats[0]!,
    mode: opts?.mode ?? "stepped",
    selectedObjectId: null,
    inspectOpen: false,
  }
}

export function reduceSceneController<TBeat extends string>(
  state: SceneControllerSnapshot<TBeat>,
  action: SceneControllerAction<TBeat>,
): SceneControllerSnapshot<TBeat> {
  const last = Math.max(state.beats.length - 1, 0)

  switch (action.type) {
    case "pause":
      return { ...state, mode: "paused" }
    case "resume":
      return { ...state, mode: state.mode === "stepped" ? "autoplay" : "autoplay" }
    case "setMode":
      return { ...state, mode: action.mode }
    case "stepForward": {
      const beatIndex = Math.min(state.beatIndex + 1, last)
      return {
        ...state,
        mode: "stepped",
        beatIndex,
        beat: state.beats[beatIndex] ?? state.beat,
      }
    }
    case "stepBack": {
      const beatIndex = Math.max(state.beatIndex - 1, 0)
      return {
        ...state,
        mode: "stepped",
        beatIndex,
        beat: state.beats[beatIndex] ?? state.beat,
      }
    }
    case "replay":
      return {
        ...state,
        beatIndex: 0,
        beat: state.beats[0] ?? state.beat,
        mode: "stepped",
        // selection preserved on purpose
      }
    case "reset":
      return createSceneControllerState(state.beats, { mode: "stepped", beatIndex: 0 })
    case "selectObject":
      return {
        ...state,
        selectedObjectId: action.id,
        inspectOpen: action.id != null,
        // beatIndex unchanged
      }
    case "inspect":
      return { ...state, inspectOpen: action.open }
    case "setBeatIndex": {
      const beatIndex = Math.min(Math.max(action.index, 0), last)
      return {
        ...state,
        beatIndex,
        beat: state.beats[beatIndex] ?? state.beat,
        mode: "stepped",
      }
    }
    case "setBeat": {
      const beatIndex = state.beats.indexOf(action.beat)
      if (beatIndex < 0) return state
      return { ...state, beatIndex, beat: action.beat, mode: "stepped" }
    }
    default:
      return state
  }
}
