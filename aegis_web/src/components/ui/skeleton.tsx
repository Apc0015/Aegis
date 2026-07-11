import { cn } from "@/lib/utils";

/** Shimmering skeleton block for loading content (not a spinner). */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-surface",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer",
        "after:bg-gradient-to-r after:from-transparent after:via-ink/5 after:to-transparent",
        className,
      )}
      aria-hidden
    />
  );
}
