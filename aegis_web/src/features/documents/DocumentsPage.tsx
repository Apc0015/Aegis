import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2, UploadCloud, Loader2 } from "lucide-react";
import {
  deleteDocument,
  listDocuments,
  listProjects,
  uploadDocuments,
} from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { RAG_MODES } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { ErrorBanner } from "@/components/ErrorBanner";
import { cn, titleize } from "@/lib/utils";

export function DocumentsPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const canDelete = user?.role !== "employee";

  const [projectId, setProjectId] = useState("general");
  const [ragMode, setRagMode] = useState("general");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const docs = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => listDocuments(projectId),
  });

  const upload = useMutation({
    mutationFn: (files: File[]) =>
      uploadDocuments({ projectId, ragMode, files, onProgress: setProgress }),
    onMutate: () => {
      setError(null);
      setProgress(0);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", projectId] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Upload failed"),
    onSettled: () => setProgress(null),
  });

  const remove = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId, projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", projectId] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Delete failed"),
  });

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    upload.mutate(Array.from(list));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        description="Upload PDF, DOCX, TXT, or MD files. Max 50 MB each."
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-36"
            >
              <option value="general">General</option>
              {projects.data?.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.project_name || titleize(p.project_id)}
                </option>
              ))}
            </Select>
            <Select
              value={ragMode}
              onChange={(e) => setRagMode(e.target.value)}
              className="w-36"
            >
              {RAG_MODES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </Select>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div
        role="button"
        tabIndex={0}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) =>
          (e.key === "Enter" || e.key === " ") && fileRef.current?.click()
        }
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-12 text-center transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30",
          dragging
            ? "border-accent bg-accent/8"
            : "border-border-strong bg-surface/40 hover:border-accent/50 hover:bg-surface/70",
        )}
      >
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-elevated">
          {upload.isPending ? (
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
          ) : (
            <UploadCloud className="h-5 w-5 text-ink-muted" />
          )}
        </div>
        {upload.isPending ? (
          <p className="text-sm text-ink-muted">
            Indexing…{" "}
            {progress != null && (
              <span className="font-mono text-accent">
                {Math.round(progress * 100)}%
              </span>
            )}
          </p>
        ) : (
          <div className="space-y-0.5">
            <p className="text-sm text-ink">
              Drop files here, or click to browse
            </p>
            <p className="font-mono text-2xs text-ink-faint">
              → project “{projectId}”
            </p>
          </div>
        )}
      </div>

      <Card>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <span className="text-sm font-medium text-ink">Indexed documents</span>
          <span className="font-mono text-2xs text-ink-faint">
            {docs.data?.length ?? 0} file{docs.data?.length === 1 ? "" : "s"}
          </span>
        </div>
        {docs.isLoading ? (
          <div className="space-y-px p-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : docs.data && docs.data.length > 0 ? (
          <div className="divide-y divide-border">
            {docs.data.map((d) => (
              <div
                key={d.doc_id}
                className="group flex items-center gap-3 px-5 py-3 transition-colors hover:bg-surface/40"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-elevated text-ink-muted">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-ink">{d.filename}</div>
                  <div className="mt-0.5 font-mono text-2xs text-ink-faint">
                    {d.chunks_count} chunk{d.chunks_count === 1 ? "" : "s"} ·{" "}
                    {d.doc_id}
                  </div>
                </div>
                {canDelete && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => remove.mutate(d.doc_id)}
                    disabled={remove.isPending}
                    aria-label={`Delete ${d.filename}`}
                    className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-danger"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState
              icon={FileText}
              title="No documents in this project"
              description="Upload files above to index them for retrieval."
            />
          </div>
        )}
      </Card>
    </div>
  );
}
