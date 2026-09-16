export const CONTINUE_AFTER_STOP_TEXT = "Continue"

export function isStopPlaceholder(text: string): boolean {
  return /^\s*stopped\.?\s*$/i.test(text)
}
