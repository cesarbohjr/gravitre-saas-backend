import { cn } from "@/lib/utils";
import React from "react";

export const Container = <T extends React.ElementType = "div">({
  children,
  className,
  as,
  id,
}: {
  children: React.ReactNode;
  className?: string;
  as?: T;
  id?: string;
}) => {
  const Component = as || "div";
  return (
    <Component id={id} className={cn("max-w-7xl mx-auto", className)}>
      {children}
    </Component>
  );
};
