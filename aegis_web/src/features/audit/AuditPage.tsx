import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ScrollText, RefreshCw, Search } from "lucide-react";
import { exportAuditCsv, getAuditLog } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { ErrorBanner } from "@/components/ErrorBanner";
import { formatTimestamp } from "@/lib/utils";

export function AuditPage() {
  const [search, setSearch] = useState("");
  const [verdict, setVerdict] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const audit = useQuery({
    queryKey: ["audit", 500],
    queryFn: () => getAuditLog(500),
    retry: false,
  });

  const rows = useMemo(() => {
    const data = audit.data ?? [];
    return data.filter((r) => {
      if (verdict !== "all" && r.access_verdict !== verdict) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          r.query_text.toLowerCase().includes(q) ||
          r.user_id.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [audit.data, search, verdict]);

  async function onExport() {
    setError(null);
    setExporting(true);
    try {
      const blob = await exportAuditCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "aegis_audit_export.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed — no records or server error.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit log"
        description="Append-only record of every query. Admin only."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => audit.refetch()}
              disabled={audit.isFetching}
            >
              <RefreshCw
                className={audit.isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"}
              />
              Refresh
            </Button>
            <Button size="sm" onClick={onExport} disabled={exporting}>
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </>
        }
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <Input
            placeholder="Search query or user…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={verdict}
          onChange={(e) => setVerdict(e.target.value)}
          className="w-40"
        >
          <option value="all">All verdicts</option>
          <option value="PERMITTED">Permitted</option>
          <option value="ALLOWED">Allowed</option>
          <option value="DENIED">Denied</option>
        </Select>
        <span className="ml-auto font-mono text-2xs text-ink-faint">
          {rows.length} record{rows.length === 1 ? "" : "s"}
        </span>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface/50 text-left font-mono text-2xs uppercase tracking-[0.1em] text-ink-faint">
                <th className="px-4 py-2.5 font-medium">Time</th>
                <th className="px-4 py-2.5 font-medium">User</th>
                <th className="px-4 py-2.5 font-medium">Query</th>
                <th className="px-4 py-2.5 font-medium">Depts</th>
                <th className="px-4 py-2.5 font-medium">Verdict</th>
                <th className="px-4 py-2.5 font-medium">Conf.</th>
                <th className="px-4 py-2.5 font-medium">Route</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {audit.isLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3" colSpan={7}>
                      <Skeleton className="h-4 w-full" />
                    </td>
                  </tr>
                ))
              ) : rows.length > 0 ? (
                rows.map((r) => (
                  <tr
                    key={r.id}
                    className="transition-colors hover:bg-surface/40"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-2xs text-ink-faint">
                      {formatTimestamp(r.timestamp)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <span className="text-ink">{r.user_id}</span>
                      <span className="ml-1.5 font-mono text-2xs text-ink-faint">
                        {r.user_role}
                      </span>
                    </td>
                    <td
                      className="max-w-[280px] truncate px-4 py-2.5 text-ink-muted"
                      title={r.query_text}
                    >
                      {r.query_text}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-2xs text-ink-faint">
                      {r.project_id ?? "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge
                        variant={
                          r.access_verdict === "DENIED" ? "danger" : "success"
                        }
                      >
                        {r.access_verdict}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-2xs tabular text-ink-muted">
                      {r.confidence_score != null
                        ? `${(r.confidence_score * 100).toFixed(0)}%`
                        : "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-2xs text-ink-faint">
                      {r.routing_path ?? "—"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-4">
                    <EmptyState icon={ScrollText} title="No matching records" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
