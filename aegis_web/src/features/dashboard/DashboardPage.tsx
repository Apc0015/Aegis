import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Activity, ArrowRight, MessageSquare, FileText, FlaskConical } from "lucide-react";
import { getHealth, getAuditLog, listProjects } from "@/api/endpoints";
import { useAuth } from "@/auth/AuthContext";
import { Card } from "@/components/ui/card";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/page-header";
import { formatTimestamp } from "@/lib/utils";

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0 px-4 py-3 sm:px-5">
      <div className="font-mono text-2xs uppercase tracking-[0.12em] text-ink-faint">
        {label}
      </div>
      <div className="mt-1 truncate font-mono text-sm text-ink">{value}</div>
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });
  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const audit = useQuery({
    queryKey: ["audit", 8],
    queryFn: () => getAuditLog(8),
    enabled: isAdmin,
    retry: false,
  });

  const h = health.data;
  const tone =
    h?.status === "ok"
      ? "success"
      : h?.status === "degraded"
        ? "warning"
        : h?.status === "error"
          ? "danger"
          : "muted";

  return (
    <div className="space-y-7">
      <PageHeader
        title="Dashboard"
        description={`Welcome back, ${user?.userId}.`}
      />

      {/* Sample-data notice — shown only while running on the bundled demo dataset */}
      {h?.demo_mode && (
        <div className="flex items-start gap-3 rounded-lg border border-accent/25 bg-accent/[0.06] px-4 py-3">
          <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <div className="min-w-0 text-[0.8125rem] leading-relaxed text-ink-muted">
            <span className="font-medium text-ink">Sample data.</span>{" "}
            You're exploring Aegis with a bundled demo dataset — a fictional
            healthcare company (employees, payroll, patients, HIPAA logs). Query
            it freely; the data firewall still governs every answer by your role.
            Connect your own sources to replace it.
          </div>
        </div>
      )}

      {/* System status panel */}
      <Card>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <StatusDot tone={tone} pulse={tone === "success"} />
            <span className="text-sm font-medium text-ink">System status</span>
          </div>
          {h ? (
            <Badge
              variant={
                tone === "success"
                  ? "success"
                  : tone === "warning"
                    ? "warning"
                    : "danger"
              }
            >
              {h.message || h.status}
            </Badge>
          ) : (
            <Skeleton className="h-5 w-24" />
          )}
        </div>
        <div className="grid grid-cols-2 divide-x divide-y divide-border sm:grid-cols-3 lg:grid-cols-5 lg:divide-y-0">
          {h ? (
            <>
              <Metric label="LLM" value={h.llm_model} />
              <Metric label="Provider" value={h.llm_provider} />
              <Metric label="Embeddings" value={h.embed_provider} />
              <Metric
                label="Database"
                value={
                  <span className={h.db_connected ? "text-success" : "text-danger"}>
                    {h.db_connected ? "connected" : "offline"}
                  </span>
                }
              />
              <Metric
                label="Projects"
                value={<span className="tabular">{projects.data?.length ?? "—"}</span>}
              />
            </>
          ) : (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-5 py-3">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="mt-2 h-4 w-24" />
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Link
          to="/chat"
          className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/40 hover:bg-elevated/60"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/12 text-accent">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-ink">Start a chat</div>
            <div className="text-2xs text-ink-faint">
              Ask a governed question
            </div>
          </div>
          <ArrowRight className="h-4 w-4 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
        </Link>
        <Link
          to="/documents"
          className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/40 hover:bg-elevated/60"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/12 text-accent">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-ink">Upload documents</div>
            <div className="text-2xs text-ink-faint">Index new sources</div>
          </div>
          <ArrowRight className="h-4 w-4 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
        </Link>
      </div>

      {/* Recent activity (admin) */}
      {isAdmin && (
        <Card>
          <div className="flex items-center gap-2 border-b border-border px-5 py-3.5">
            <Activity className="h-4 w-4 text-ink-muted" />
            <span className="text-sm font-medium text-ink">Recent activity</span>
            <Link
              to="/audit"
              className="ml-auto text-2xs text-accent hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="divide-y divide-border">
            {audit.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="px-5 py-3">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-40" />
                </div>
              ))
            ) : audit.data && audit.data.length > 0 ? (
              audit.data.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-surface/40"
                >
                  <div className="min-w-0">
                    <div className="truncate text-[0.8125rem] text-ink">
                      {r.query_text}
                    </div>
                    <div className="mt-0.5 font-mono text-2xs text-ink-faint">
                      {r.user_id} · {r.user_role} · {formatTimestamp(r.timestamp)}
                    </div>
                  </div>
                  <Badge
                    variant={r.access_verdict === "DENIED" ? "danger" : "success"}
                  >
                    {r.access_verdict}
                  </Badge>
                </div>
              ))
            ) : (
              <p className="px-5 py-6 text-center text-sm text-ink-faint">
                No activity yet.
              </p>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
