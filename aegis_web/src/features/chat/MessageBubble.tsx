import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { ResultMeta } from "./ResultMeta";
import type { QueryResult } from "@/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: QueryResult;
  isPartial?: boolean;
  error?: boolean;
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="max-w-[85%] rounded-xl rounded-tr-sm bg-accent px-4 py-2.5 text-sm leading-relaxed text-accent-ink shadow-panel">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-fade-up">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated text-accent">
        <Bot className="h-4 w-4" />
      </div>
      <div
        className={cn(
          "min-w-0 max-w-[85%] rounded-xl rounded-tl-sm border px-4 py-3 text-sm leading-relaxed",
          message.error
            ? "border-danger/30 bg-danger/10 text-danger"
            : "border-border bg-card text-ink",
        )}
      >
        <div className="whitespace-pre-wrap break-words">
          {message.content || (message.isPartial ? "" : "…")}
          {message.isPartial && (
            <span className="ml-0.5 inline-block h-4 w-[3px] translate-y-[3px] animate-blink rounded-full bg-accent align-middle" />
          )}
        </div>
        {message.result && <ResultMeta result={message.result} />}
      </div>
    </div>
  );
}
