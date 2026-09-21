"use client"

import { useCallback, useReducer } from "react"
import {
  createSceneControllerState,
  reduceSceneController,
  type PlaybackMode,
  type SceneControllerAction,
  type SceneControllerSnapshot,
} from "./scene-controller"

export function useSceneController<TBeat extends string>(
  beats: readonly TBeat[],
  opts?: { mode?: PlaybackMode; beatIndex?: number },
) {
  const [state, dispatch] = useReducer(
    (s: SceneControllerSnapshot<TBeat>, a: SceneControllerAction<TBeat>) => reduceSceneController(s, a),
    undefined,
    () => createSceneControllerState(beats, opts),
  )

  const pause = useCallback(() => dispatch({ type: "pause" }), [])
  const resume = useCallback(() => dispatch({ type: "resume" }), [])
  const stepForward = useCallback(() => dispatch({ type: "stepForward" }), [])
  const stepBack = useCallback(() => dispatch({ type: "stepBack" }), [])
  const replay = useCallback(() => dispatch({ type: "replay" }), [])
  const reset = useCallback(() => dispatch({ type: "reset" }), [])
  const selectObject = useCallback((id: string | null) => dispatch({ type: "selectObject", id }), [])
  const setInspect = useCallback((open: boolean) => dispatch({ type: "inspect", open }), [])
  const setBeatIndex = useCallback((index: number) => dispatch({ type: "setBeatIndex", index }), [])
  const setBeat = useCallback((beat: TBeat) => dispatch({ type: "setBeat", beat }), [])
  const setMode = useCallback((mode: PlaybackMode) => dispatch({ type: "setMode", mode }), [])

  return {
    ...state,
    pause,
    resume,
    stepForward,
    stepBack,
    replay,
    reset,
    selectObject,
    setInspect,
    setBeatIndex,
    setBeat,
    setMode,
    dispatch,
  }
}
