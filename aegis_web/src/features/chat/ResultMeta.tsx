import {
  Globe,
  Database,
  ShieldCheck,
  Sparkles,
  Layers,
  Gauge,
  FileText,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatLatency } from "@/lib/utils";
import type { QueryResult, Verdict } from "@/api/types";

function verdictVariant(v: Verdict): "success" | "warning" | "danger" {
  return v === "high" ? "success" : v === "medium" ? "warning" : "danger";
}

export function ConfidenceBadge({
  verdict,
  score,
}: {
  verdict: Verdict;
  score: number;
}) {
  return (
    <Badge variant={verdictVariant(verdict)}>
      <Gauge className="h-3 w-3" />
      <span className="capitalize">{verdict}</span>
      <span className="tabular font-mono">{(score * 100).toFixed(0)}%</span>
    </Badge>
  );
}

const ROUTING_LABEL: Record<string, string> = {
  direct: "Direct",
  disclaimer: "Low-confidence",
  web: "Web fallback",
  refuse: "Refused",
  denied: "Access denied",
  direct_llm: "Direct LLM",
};

export function ResultMeta({ result }: { result: QueryResult }) {
  const firewallActive =
    result.columns_blocked.length > 0 || result.columns_anonymized.length > 0;

  return (
    <div className="mt-3.5 space-y-2.5 border-t border-border pt-3">
      <div className="flex flex-wrap gap-1.5">
        <ConfidenceBadge verdict={result.verdict} score={result.confidence} />
        <Badge variant="outline">
          {ROUTING_LABEL[result.routing_path] ?? result.routing_path}
        </Badge>
        {result.db_triggered && (
          <Badge variant="accent">
            <Database className="h-3 w-3" />
            Database
          </Badge>
        )}
        {result.web_used && (
          <Badge variant="neutral">
            <Globe className="h-3 w-3" />
            Web
          </Badge>
        )}
        {result.reranker_used && (
          <Badge variant="neutral">
            <Layers className="h-3 w-3" />
            Reranked
          </Badge>
        )}
        {result.cross_model_eval && (
          <Badge variant="neutral">
            <Sparkles className="h-3 w-3" />
            Cross-model
          </Badge>
        )}
        {firewallActive && (
          <Badge variant="warning">
            <ShieldCheck className="h-3 w-3" />
            Firewall · {result.columns_blocked.length} blocked ·{" "}
            {result.columns_anonymized.length} masked
          </Badge>
        )}
      </div>

      {result.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.sources.map((s, i) => (
            <span
              key={i}
              title={s.text}
              className="inline-flex max-w-[260px] items-center gap-1.5 truncate rounded-md border border-border bg-surface/70 px-2 py-1 text-2xs text-ink-muted"
            >
              <FileText className="h-3 w-3 shrink-0 text-ink-faint" />
              <span className="font-mono text-accent/90">[{i + 1}]</span>
              <span className="truncate">{s.source}</span>
              {s.department && (
                <span className="shrink-0 text-ink-faint">· {s.department}</span>
              )}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-2xs text-ink-faint">
        <span>{result.model_used}</span>
        <span className="text-border-strong">•</span>
        <span className="tabular">{formatLatency(result.latency_ms)}</span>
        <span className="text-border-strong">•</span>
        <span>
          {result.chunks_used} chunk{result.chunks_used === 1 ? "" : "s"}
        </span>
        {result.cached && (
          <>
            <span className="text-border-strong">•</span>
            <span className="text-accent/80">cached</span>
          </>
        )}
      </div>
    </div>
  );
}
