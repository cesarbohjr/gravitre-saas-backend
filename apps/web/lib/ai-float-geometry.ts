/**
 * Phase 5 — session persistence for Float window size/position with viewport clamp.
 */

import type { WindowSize } from "@/hooks/use-window-resize"

export const AI_FLOAT_GEOMETRY_STORAGE_KEY = "gravitre.ai.float.geometry.v1"

export const GRAVITRE_FLOAT_DEFAULT_SIZE: WindowSize = { width: 520, height: 560 }
export const GRAVITRE_FLOAT_MIN_SIZE: WindowSize = { width: 400, height: 420 }
export const GRAVITRE_FLOAT_MAX_SIZE: WindowSize = { width: 720, height: 760 }

export type AiFloatGeometry = {
  width: number
  height: number
  /** framer-motion drag translate X (px) */
  x: number
  /** framer-motion drag translate Y (px) */
  y: number
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(Math.max(n, min), max)
}

export function clampFloatSize(size: WindowSize, viewport: { width: number; height: number }): WindowSize {
  const maxW = Math.min(GRAVITRE_FLOAT_MAX_SIZE.width, Math.max(GRAVITRE_FLOAT_MIN_SIZE.width, viewport.width - 24))
  const maxH = Math.min(GRAVITRE_FLOAT_MAX_SIZE.height, Math.max(GRAVITRE_FLOAT_MIN_SIZE.height, viewport.height - 24))
  return {
    width: clamp(size.width, GRAVITRE_FLOAT_MIN_SIZE.width, maxW),
    height: clamp(size.height, GRAVITRE_FLOAT_MIN_SIZE.height, maxH),
  }
}

/** Keep the window reachable — clamp drag translate into the usable viewport. */
export function clampFloatTranslate(
  pos: { x: number; y: number },
  viewport: { width: number; height: number },
): { x: number; y: number } {
  const margin = 48
  return {
    x: clamp(pos.x, -(viewport.width - margin), viewport.width - margin),
    y: clamp(pos.y, -(viewport.height - margin), viewport.height - margin),
  }
}

export function readStoredFloatGeometry(
  viewport: { width: number; height: number } | null,
): AiFloatGeometry | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.sessionStorage.getItem(AI_FLOAT_GEOMETRY_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<AiFloatGeometry>
    if (
      typeof parsed.width !== "number" ||
      typeof parsed.height !== "number" ||
      typeof parsed.x !== "number" ||
      typeof parsed.y !== "number"
    ) {
      return null
    }
    const vp = viewport ?? { width: window.innerWidth, height: window.innerHeight }
    const size = clampFloatSize({ width: parsed.width, height: parsed.height }, vp)
    const pos = clampFloatTranslate({ x: parsed.x, y: parsed.y }, vp)
    return { ...size, ...pos }
  } catch {
    return null
  }
}

export function writeStoredFloatGeometry(geometry: AiFloatGeometry): void {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(AI_FLOAT_GEOMETRY_STORAGE_KEY, JSON.stringify(geometry))
  } catch {
    // quota / private mode — ignore
  }
}
