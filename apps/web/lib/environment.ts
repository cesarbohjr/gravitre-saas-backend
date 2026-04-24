export function getEnvironmentHeader(): string {
  if (typeof window === "undefined") {
    return "default";
  }
  const value = window.localStorage.getItem("gravitre_env") ?? "default";
  const trimmed = value.trim();
  return trimmed || "default";
}
