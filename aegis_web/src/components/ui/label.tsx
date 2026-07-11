import * as React from "react";
import { cn } from "@/lib/utils";

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-[0.8125rem] font-medium leading-none text-ink-muted",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
