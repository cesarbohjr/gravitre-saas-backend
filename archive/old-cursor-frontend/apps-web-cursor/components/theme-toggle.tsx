"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * FE-00: Theme toggle. Brand Spec §3.4 — .dark on <html>.
 * No component logic branches on theme; only CSS vars change.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const root = document.documentElement;
    setDark(root.classList.contains("dark"));
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [dark, mounted]);

  if (!mounted) return null;

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setDark((d) => !d)}
      className={cn("rounded-md")}
    >
      {dark ? "Light" : "Dark"}
    </Button>
  );
}
