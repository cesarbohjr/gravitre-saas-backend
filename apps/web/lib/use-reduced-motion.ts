"use client"

import { useSyncExternalStore } from "react"

/**
 * Hydration-safe `prefers-reduced-motion` hook.
 *
 * framer-motion's `useReducedMotion()` reads the media query during the first
 * client render, so on a device with Reduce Motion turned on the client's first
 * render differs from the server HTML (which always assumes motion). React then
 * either throws away the server tree (error #418) or keeps the server's
 * attributes without patching them, which left reveal wrappers stuck at
 * `opacity: 0`. This hook returns `false` while hydrating, exactly like the
 * server, and switches to the real preference right after.
 */
const QUERY = "(prefers-reduced-motion: reduce)"

function subscribe(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {}
  const mq = window.matchMedia(QUERY)
  mq.addEventListener?.("change", onChange)
  return () => mq.removeEventListener?.("change", onChange)
}

function getSnapshot() {
  return typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(QUERY).matches
}

function getServerSnapshot() {
  return false
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
