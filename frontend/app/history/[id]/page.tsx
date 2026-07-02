"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { BrandLoader } from "@/components/BrandLoader";
import { getJson } from "@/components/api";
import { useAuth } from "@/components/auth";

/* Read-only viewer for a past conversation ("chat section"). Rehydrates the
   stored messages so a returning user can revisit everything they generated.
   Rich prediction details live in each assistant message's `payload`. */

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload: any | null;
  created_at: string;
};
type Thread = {
  conversation: { id: string; tool: string; title: string | null; created_at: string };
  messages: Message[];
};

const TOOL_HREF: Record<string, string> = {
  predict: "/predict",
  documents: "/predict",
  assistant: "/assistant",
  statutes: "/statutes",
};

export default function HistoryThread() {
  const { id } = useParams<{ id: string }>();
  const { user, ready } = useAuth();
  const [thread, setThread] = useState<Thread | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setError("Sign in to view your saved history.");
      return;
    }
    getJson<Thread>(`/api/conversations/${id}`)
      .then(setThread)
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load this conversation."));
  }, [id, user, ready]);

  return (
    <WorkspaceShell>
      <main className="container-page max-w-3xl py-12">
        {error ? (
          <div className="card p-6 text-sm text-ink/70">{error}</div>
        ) : !thread ? (
          <div className="grid place-items-center py-24">
            <BrandLoader />
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <span className="eyebrow"><span className="h-px w-6 bg-gold-500" />Saved session</span>
                <h1 className="mt-3 font-serif text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
                  {thread.conversation.title || "Conversation"}
                </h1>
                <p className="mt-1 text-xs text-ink/50">
                  {new Date(thread.conversation.created_at).toLocaleString()}
                </p>
              </div>
              <Link
                href={TOOL_HREF[thread.conversation.tool] || "/predict"}
                className="btn-primary px-4 py-2 text-sm"
              >
                Continue in tool
              </Link>
            </div>

            <div className="mt-8 space-y-4">
              {thread.messages.map((m) => (
                <ThreadMessage key={m.id} msg={m} />
              ))}
            </div>
          </>
        )}
      </main>
    </WorkspaceShell>
  );
}

function ThreadMessage({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-navy-900 px-4 py-2.5 text-sm leading-relaxed text-cream">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-3">
        <div className="whitespace-pre-wrap rounded-2xl border border-ink/10 bg-surface/70 px-4 py-3 text-sm leading-relaxed text-ink/85">
          {msg.content || "No content"}
        </div>
        {msg.payload && <PredictionSummary payload={msg.payload} />}
      </div>
    </div>
  );
}

/* A compact, defensive render of whatever structured data we stored. We don't
   assume a particular tool's shape — we show the fields that are present. */
function PredictionSummary({ payload }: { payload: any }) {
  const outcome = payload.likely_outcome;
  const winProb = payload.win_probability;
  const confidence = payload.confidence;
  const cited = payload.cited_cases as Array<{ case_name?: string; citation?: string }> | undefined;
  const statutes = payload.statutes as Array<{ act?: string; section?: string }> | undefined;

  const hasStats = outcome || typeof winProb === "number" || confidence;
  if (!hasStats && !cited?.length && !statutes?.length) return null;

  return (
    <div className="rounded-2xl border border-ink/10 bg-surface/50 px-4 py-3 text-sm">
      {hasStats && (
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-ink/75">
          {outcome && (
            <span><span className="text-ink/45">Outcome:</span> <span className="font-semibold">{outcome}</span></span>
          )}
          {typeof winProb === "number" && (
            <span><span className="text-ink/45">Win likelihood:</span> <span className="font-semibold">{Math.round(winProb * 100)}%</span></span>
          )}
          {confidence && (
            <span><span className="text-ink/45">Confidence:</span> <span className="font-semibold capitalize">{confidence}</span></span>
          )}
        </div>
      )}
      {statutes?.length ? (
        <div className="mt-2 text-xs text-ink/60">
          <span className="font-semibold uppercase tracking-wider text-ink/40">Statutes</span>
          <ul className="mt-1 space-y-0.5">
            {statutes.map((s, i) => (
              <li key={i}>{[s.act, s.section].filter(Boolean).join(" · ")}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {cited?.length ? (
        <div className="mt-2 text-xs text-ink/60">
          <span className="font-semibold uppercase tracking-wider text-ink/40">Cases relied on</span>
          <ul className="mt-1 space-y-0.5">
            {cited.map((c, i) => (
              <li key={i}>{c.case_name}{c.citation ? ` · ${c.citation}` : ""}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
