import { useQuery } from "@tanstack/react-query";
import { LogOut, Menu } from "lucide-react";
import { getHealth } from "@/api/endpoints";
import { useAuth } from "@/auth/AuthContext";
import { RoleBadge } from "@/components/RoleBadge";
import { StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { user, logout } = useAuth();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const tone =
    health?.status === "ok"
      ? "success"
      : health?.status === "degraded"
        ? "warning"
        : health?.status === "error"
          ? "danger"
          : "muted";

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-bg/70 px-4 backdrop-blur-xl sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="flex min-w-0 items-center gap-2.5 rounded-md border border-border bg-surface/60 px-3 py-1.5">
          <StatusDot tone={tone} pulse={tone === "success"} />
          <span className="hidden truncate font-mono text-xs text-ink-muted sm:inline">
            {health ? `${health.llm_provider}/${health.llm_model}` : "connecting…"}
          </span>
          <span className="font-mono text-xs text-ink-muted sm:hidden">
            {health?.status ?? "…"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <div className="hidden items-center gap-2.5 sm:flex">
            <RoleBadge role={user.role} />
            <span className="text-sm text-ink-muted">{user.userId}</span>
          </div>
        )}
        <div className="h-5 w-px bg-border" aria-hidden />
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Sign out</span>
        </Button>
      </div>
    </header>
  );
}
