import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-2xs font-medium tracking-normal",
  {
    variants: {
      variant: {
        neutral: "border-border bg-surface text-ink-muted",
        accent: "border-accent/25 bg-accent/12 text-accent",
        success: "border-success/25 bg-success/12 text-success",
        warning: "border-warning/25 bg-warning/12 text-warning",
        danger: "border-danger/30 bg-danger/12 text-danger",
        outline: "border-border text-ink-muted",
      },
      size: {
        sm: "px-1.5 py-0 text-2xs",
        md: "px-2 py-0.5 text-2xs",
      },
    },
    defaultVariants: { variant: "neutral", size: "md" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, size, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, size }), className)} {...props} />
  );
}

/** A tiny status dot with an optional soft pulse. */
export function StatusDot({
  tone,
  pulse,
}: {
  tone: "success" | "warning" | "danger" | "muted";
  pulse?: boolean;
}) {
  const color =
    tone === "success"
      ? "bg-success"
      : tone === "warning"
        ? "bg-warning"
        : tone === "danger"
          ? "bg-danger"
          : "bg-ink-faint";
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full rounded-full opacity-60",
            color,
            "animate-pulse-ring",
          )}
        />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", color)} />
    </span>
  );
}
