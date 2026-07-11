import { cn } from "@/lib/utils";

/** Aegis mark: a shield glyph carrying an "A", nodding to the data firewall. */
export function AegisLogo({
  className,
  showWordmark = true,
}: {
  className?: string;
  showWordmark?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <svg
        width="30"
        height="30"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden
        className="shrink-0"
      >
        <defs>
          <linearGradient id="aegis-mark" x1="0" y1="0" x2="32" y2="32">
            <stop offset="0" stopColor="oklch(0.74 0.155 264)" />
            <stop offset="1" stopColor="oklch(0.62 0.16 272)" />
          </linearGradient>
        </defs>
        <path
          d="M16 2.5 4.5 6.4v8.3c0 6.9 4.7 12 11.5 14.8C22.8 26.7 27.5 21.6 27.5 14.7V6.4L16 2.5Z"
          fill="url(#aegis-mark)"
        />
        <path
          d="M16 2.5 4.5 6.4v8.3c0 6.9 4.7 12 11.5 14.8C22.8 26.7 27.5 21.6 27.5 14.7V6.4L16 2.5Z"
          stroke="oklch(1 0 0 / 0.18)"
          strokeWidth="0.6"
        />
        <path
          d="M16 10 11.8 22M16 10l4.2 12M13.55 17h4.9"
          stroke="oklch(0.16 0.02 265)"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      {showWordmark && (
        <div className="leading-none">
          <div className="text-[0.95rem] font-semibold tracking-tight text-ink">
            AEGIS
          </div>
          <div className="mt-1 font-mono text-[0.5625rem] uppercase tracking-[0.18em] text-ink-faint">
            Enterprise RAG
          </div>
        </div>
      )}
    </div>
  );
}
