import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-surface/40 px-6 py-16 text-center">
      <div className="relative">
        <div className="absolute inset-0 rounded-xl bg-accent/10 blur-lg" aria-hidden />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-elevated">
          <Icon className="h-5 w-5 text-ink-muted" />
        </div>
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-ink">{title}</p>
        {description ? (
          <p className="mx-auto max-w-sm text-[0.8125rem] leading-relaxed text-ink-faint">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
