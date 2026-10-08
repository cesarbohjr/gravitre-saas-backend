import { cn } from "@/lib/utils";
import React from "react";

export const Scale = ({ className }: { className?: string }) => {
  return (
    <div
      className={cn(
        "absolute inset-0 z-10 m-auto h-full w-full rounded-lg border border-(--pattern-fg) bg-card bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px]",
        className,
      )}
    ></div>
  );
};
