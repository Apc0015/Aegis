import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} />;
}

export function FullPageSpinner({ label }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[240px] w-full flex-col items-center justify-center gap-3 text-ink-faint">
      <Loader2 className="h-5 w-5 animate-spin text-accent" />
      {label ? <p className="text-sm">{label}</p> : null}
    </div>
  );
}
