import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium",
    "transition-[background-color,color,box-shadow,transform,border-color] duration-150 ease-out-quart",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
    "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 select-none",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-accent-ink hover:bg-accent-strong shadow-[inset_0_1px_0_oklch(1_0_0/0.12)]",
        secondary:
          "bg-elevated text-ink border border-border hover:border-border-strong hover:bg-elevated/80",
        outline:
          "border border-border-strong text-ink-muted hover:text-ink hover:bg-surface",
        ghost: "text-ink-muted hover:bg-surface hover:text-ink",
        soft: "bg-accent/12 text-accent hover:bg-accent/20",
        destructive: "bg-danger text-white hover:bg-danger/90",
      },
      size: {
        sm: "h-8 px-3 text-[0.8125rem] rounded-md",
        md: "h-9 px-4 text-sm",
        lg: "h-11 px-5 text-sm",
        icon: "h-9 w-9",
        "icon-sm": "h-8 w-8 rounded-md",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  ),
);
Button.displayName = "Button";
