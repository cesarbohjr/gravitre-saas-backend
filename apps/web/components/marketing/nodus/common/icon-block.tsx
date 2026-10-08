import { cn } from "@/lib/utils";

export const IconBlock = ({
  icon,
  className,
  children,
}: {
  icon: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "relative flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-card shadow-md",
        className,
      )}
    >
      {icon}
      {children}
    </div>
  );
};
