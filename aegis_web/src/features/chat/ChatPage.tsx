import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUp, Square, Sparkles } from "lucide-react";
import { listProjects } from "@/api/endpoints";
import { streamQuery } from "@/api/sse";
import { RAG_MODES } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Kbd } from "@/components/ui/page-header";
import { AegisLogo } from "@/components/AegisLogo";
import { MessageBubble, type ChatMessage } from "./MessageBubble";
import { titleize } from "@/lib/utils";

const uid = () => Math.random().toString(36).slice(2);

const EXAMPLES = [
  "What is the remote work policy?",
  "How many days of annual leave do employees get?",
  "Summarize the patient intake procedure",
  "What are our compliance requirements for records?",
];

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [projectId, setProjectId] = useState("general");
  const [ragMode, setRagMode] = useState("general");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const conversationId = useMemo(() => uid(), []);

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Auto-grow the composer.
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming) return;
    setInput("");

    const assistantId = uid();
    setMessages((m) => [
      ...m,
      { id: uid(), role: "user", content: q },
      { id: assistantId, role: "assistant", content: "", isPartial: true },
    ]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    const patch = (fn: (msg: ChatMessage) => ChatMessage) =>
      setMessages((m) => m.map((msg) => (msg.id === assistantId ? fn(msg) : msg)));

    try {
      for await (const ev of streamQuery({
        userQuery: q,
        projectId,
        ragMode,
        conversationId,
        signal: controller.signal,
      })) {
        if (ev.kind === "token") {
          patch((msg) => ({ ...msg, content: msg.content + ev.token }));
        } else if (ev.kind === "result") {
          patch((msg) => ({
            ...msg,
            content: msg.content || ev.data.answer,
            result: ev.data,
            isPartial: false,
          }));
        } else if (ev.kind === "error") {
          patch((msg) => ({
            ...msg,
            content: msg.content || `Error: ${ev.message}`,
            error: true,
            isPartial: false,
          }));
        } else if (ev.kind === "done") {
          patch((msg) => ({ ...msg, isPartial: false }));
        }
      }
    } catch (err) {
      patch((msg) => ({
        ...msg,
        content: msg.content || `Stream failed: ${(err as Error).message ?? err}`,
        error: true,
        isPartial: false,
      }));
    } finally {
      patch((msg) => ({ ...msg, isPartial: false }));
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col gap-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-ink">Chat</h1>
          <p className="text-2xs text-ink-faint">
            Governed by RBAC · retrieval + firewall auto-selected
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="w-40"
          >
            <option value="general">General workspace</option>
            {projects?.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.project_name || titleize(p.project_id)}
              </option>
            ))}
          </Select>
          <Select
            value={ragMode}
            onChange={(e) => setRagMode(e.target.value)}
            className="w-40"
          >
            {RAG_MODES.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-xl border border-border bg-bg/40"
      >
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 px-6 py-10 text-center">
            <div className="relative">
              <div
                className="absolute inset-0 rounded-full bg-accent/20 blur-2xl"
                aria-hidden
              />
              <AegisLogo showWordmark={false} className="relative scale-[1.8]" />
            </div>
            <div className="space-y-1.5">
              <h2 className="text-xl font-semibold tracking-tight text-ink">
                Ask Aegis anything
              </h2>
              <p className="mx-auto max-w-md text-sm leading-relaxed text-ink-muted">
                The system routes your question through role-based access and the
                data firewall, then answers from documents, the database, or the
                web — whichever fits.
              </p>
            </div>
            <div className="flex max-w-xl flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => {
                    setInput(ex);
                    taRef.current?.focus();
                  }}
                  className="group inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3.5 py-1.5 text-[0.8125rem] text-ink-muted transition-colors duration-150 hover:border-accent/40 hover:bg-accent/10 hover:text-ink"
                >
                  <Sparkles className="h-3 w-3 text-ink-faint group-hover:text-accent" />
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-5 p-5">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="rounded-xl border border-border bg-card p-2 transition-colors focus-within:border-accent/50">
        <div className="flex items-end gap-2">
          <Textarea
            ref={taRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question…"
            rows={1}
            className="max-h-52 flex-1 resize-none border-0 bg-transparent px-2 py-2 shadow-none focus-visible:ring-0"
          />
          {streaming ? (
            <Button variant="destructive" size="icon" onClick={stop} aria-label="Stop">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={() => void send(input)}
              disabled={!input.trim()}
              aria-label="Send"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="flex items-center justify-between px-2 pb-1 pt-1.5 text-2xs text-ink-faint">
          <span className="flex items-center gap-1.5">
            <Kbd>↵</Kbd> to send
            <span className="text-border-strong">·</span>
            <Kbd>⇧ ↵</Kbd> new line
          </span>
          {streaming && <span className="text-accent">streaming…</span>}
        </div>
      </div>
    </div>
  );
}
