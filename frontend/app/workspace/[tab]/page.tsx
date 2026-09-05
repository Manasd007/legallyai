"use client";

import { Suspense, useEffect, useState } from "react";
import { notFound, useParams, useRouter, useSearchParams } from "next/navigation";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { BrandLoader } from "@/components/BrandLoader";
import { ScalesIcon, ChatIcon, BookIcon } from "@/components/ui";
import { useSession, type Tool } from "@/components/session";
import { getJson } from "@/components/api";
import { AssessTab } from "@/components/tabs/AssessTab";
import { AskTab } from "@/components/tabs/AskTab";
import { LawTab } from "@/components/tabs/LawTab";
import type { StoredMessage } from "@/components/tabs/types";

type TabKey = "assess" | "ask" | "law";

const TABS: { key: TabKey; label: string; sub: string; icon: typeof ScalesIcon }[] = [
  { key: "assess", label: "Assess a case", sub: "Predict, read docs & chat", icon: ScalesIcon },
  { key: "ask", label: "Ask a question", sub: "Chat about the law", icon: ChatIcon },
  { key: "law", label: "Find the law", sub: "Acts & sections", icon: BookIcon },
];

const TOOL_TO_TAB: Record<string, TabKey> = {
  predict: "assess",
  documents: "assess",
  assistant: "ask",
  statutes: "law",
};

type Hydrated = {
  sessionId: string;
  messages: Record<TabKey, StoredMessage[]>;
};

type SessionPayload = {
  session_id: string;
  title: string | null;
  conversations: {
    id: string;
    tool: string;
    title: string | null;
    messages: StoredMessage[];
  }[];
};

export default function WorkspaceTabPage() {
  return (
    <Suspense fallback={<ShellLoader />}>
      <Workspace />
    </Suspense>
  );
}

function ShellLoader() {
  return (
    <WorkspaceShell>
      <div className="grid min-h-[60vh] place-items-center">
        <BrandLoader />
      </div>
    </WorkspaceShell>
  );
}

function Workspace() {
  const router = useRouter();
  const params = useSearchParams();
  const routeTab = String(useParams().tab || "");
  const { sessionId, matter, ready, newSession, loadSession } = useSession();

  if (!TABS.some((t) => t.key === routeTab)) notFound();
  const active = routeTab as TabKey;
  const sessionParam = params.get("session");

  const [hydrated, setHydrated] = useState<Hydrated | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionParam || sessionParam === hydrated?.sessionId) return;
    if (sessionParam === sessionId && hydrated) return;

    let cancelled = false;
    setLoadError(null);
    getJson<SessionPayload>(`/api/sessions/${sessionParam}`)
      .then((data) => {
        if (cancelled) return;
        const messages: Record<TabKey, StoredMessage[]> = { assess: [], ask: [], law: [] };
        const conv: Partial<Record<Tool, string>> = {};
        for (const c of data.conversations) {
          const tab = TOOL_TO_TAB[c.tool];
          if (!tab) continue;
          messages[tab] = messages[tab].concat(c.messages || []);

          const toolKey: Tool = tab === "assess" ? "predict" : tab === "ask" ? "assistant" : "statutes";
          conv[toolKey] = c.id;
        }

        (Object.keys(messages) as TabKey[]).forEach((k) =>
          messages[k].sort((a, b) => (a.created_at < b.created_at ? -1 : 1)),
        );
        loadSession(data.session_id, conv, data.title || null);
        setHydrated({ sessionId: data.session_id, messages });
      })
      .catch((e) => !cancelled && setLoadError(e instanceof Error ? e.message : "Couldn't load this session."));

    return () => {
      cancelled = true;
    };
  }, [sessionParam, sessionId, hydrated, loadSession]);

  function tabHref(key: TabKey) {
    return sessionParam ? `/workspace/${key}?session=${sessionParam}` : `/workspace/${key}`;
  }

  function setTab(key: TabKey) {
    router.replace(tabHref(key), { scroll: false });
  }

  function startNew() {
    newSession();
    setHydrated(null);
    router.replace(`/workspace/${active}`, { scroll: false });
  }

  if (!ready) return <ShellLoader />;

  const awaitingSession = !!sessionParam && hydrated?.sessionId !== sessionParam;

  const initial = (tab: TabKey): StoredMessage[] | undefined =>
    hydrated && hydrated.sessionId === sessionId ? hydrated.messages[tab] : undefined;

  return (
    <WorkspaceShell>

      <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-6 lg:px-8">

        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-4 border-b-2 border-ink pb-4">
          <div role="tablist" aria-label="Workspace tools" className="flex flex-wrap gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            const on = active === t.key;
            return (
              <button
                key={t.key}
                role="tab"
                aria-selected={on}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 rounded border-2 px-3.5 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] transition-[transform,box-shadow,background-color] duration-150 ${
                  on
                    ? "border-ink bg-ink text-onbrand shadow-brutal-sm"
                    : "border-ink/25 text-ink/55 hover:border-ink hover:text-ink"
                }`}
              >
                <Icon className={`h-4 w-4 ${on ? "text-gold-400" : "text-ink/40"}`} />
                {t.label}
              </button>
            );
          })}
          </div>
          <button onClick={startNew} className="btn-ghost shrink-0 gap-1.5 px-3 py-2 text-xs">
            <PlusIcon /> New session
          </button>
        </div>

        {matter && (
          <div className="mt-4 flex items-baseline gap-2">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-gold-600">
              Matter
            </span>
            <h1 className="line-clamp-1 font-serif text-base font-semibold tracking-tight text-ink">
              {matter}
            </h1>
          </div>
        )}

        <div className="mt-6 flex min-h-0 flex-1 flex-col">
          {awaitingSession ? (
            loadError ? (
              <div className="card text-sm text-ink/70">{loadError}</div>
            ) : (
              <div className="grid flex-1 place-items-center">
                <BrandLoader label="Opening your session…" />
              </div>
            )
          ) : (
            <div key={sessionId} className="flex min-h-0 flex-1 flex-col">
              <div className={active === "assess" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                <AssessTab initialMessages={initial("assess")} />
              </div>
              <div className={active === "ask" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                <AskTab initialMessages={initial("ask")} />
              </div>
              <div className={active === "law" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                <LawTab initialMessages={initial("law")} />
              </div>
            </div>
          )}
        </div>
      </main>
    </WorkspaceShell>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-3.5 w-3.5" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
