/**
 * Microphone device enumeration + persisted preference (Voice 3.0 Phase 1).
 */

export type MicDeviceOption = {
  deviceId: string
  label: string
}

const STORAGE_KEY = "gravitre:voice-mic-device:v1"

export function getStoredMicDeviceId(): string | null {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw && raw.trim() ? raw.trim() : null
  } catch {
    return null
  }
}

export function setStoredMicDeviceId(deviceId: string | null): void {
  if (typeof window === "undefined") return
  try {
    if (!deviceId) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, deviceId)
  } catch {
    /* ignore */
  }
}

export async function listMicInputDevices(): Promise<MicDeviceOption[]> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
    return []
  }
  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices
    .filter((d) => d.kind === "audioinput")
    .map((d, i) => ({
      deviceId: d.deviceId,
      label: d.label?.trim() || `Microphone ${i + 1}`,
    }))
}

export type MicFieldProfile = "near_field" | "far_field" | "auto"

const NEAR_HINTS = [
  "headset",
  "headphone",
  "earbud",
  "airpod",
  "usb audio",
  "external",
  "yeti",
  "snowball",
  "shure",
  "rode",
  "podmic",
]

const FAR_HINTS = [
  "built-in",
  "internal",
  "laptop",
  "array",
  "webcam",
  "default",
  "communications",
]

/** Heuristic near vs far-field from device label (Voice 3.0 Phase 1). */
export function inferMicFieldProfile(label: string): Exclude<MicFieldProfile, "auto"> {
  const l = label.toLowerCase()
  if (NEAR_HINTS.some((h) => l.includes(h))) return "near_field"
  if (FAR_HINTS.some((h) => l.includes(h))) return "far_field"
  return "far_field"
}

export function resolveMicFieldProfile(
  label: string,
  override?: MicFieldProfile | null,
): Exclude<MicFieldProfile, "auto"> {
  if (override && override !== "auto") return override
  return inferMicFieldProfile(label)
}
