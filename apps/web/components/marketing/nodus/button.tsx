import { cn } from "@/lib/utils";
import React from "react";

export const Button = <T extends React.ElementType = "button">({
  children,
  variant = "primary",
  className,
  as,
  ...props
}: {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "brand";
  className?: string;
  as?: T;
} & Omit<
  React.ComponentProps<T>,
  "children" | "variant" | "className" | "as"
>) => {
  const Component = as || "button";

  return (
    <Component
      {...props}
      className={cn(
        // w-fit keeps black CTAs content-sized (footer column was stretching block buttons)
        "inline-flex w-fit items-center justify-center rounded-xl px-5 py-1.5 text-center text-sm font-medium transition duration-150 active:scale-[0.98] sm:px-6 sm:py-2 sm:text-base",
        variant === "primary"
          ? "bg-charcoal-900 text-white dark:bg-white dark:text-black"
          : variant === "brand"
            ? "bg-brand text-white"
            : "border-divide border bg-white text-black transition duration-200 hover:bg-gray-300 dark:border-neutral-700 dark:bg-neutral-950 dark:text-white dark:hover:bg-neutral-800",
        className,
      )}
    >
      {children}
    </Component>
  );
};
