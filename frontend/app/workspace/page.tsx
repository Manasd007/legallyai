"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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

export default function WorkspacePage() {
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
  const { sessionId, matter, ready, newSession, loadSession } = useSession();

  const tabParam = (params.get("tab") as TabKey) || "assess";
  const sessionParam = params.get("session");
  const active: TabKey = TABS.some((t) => t.key === tabParam) ? tabParam : "assess";

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

  function setTab(key: TabKey) {
    const next = new URLSearchParams(params.toString());
    next.set("tab", key);
    router.replace(`/workspace?${next.toString()}`, { scroll: false });
  }

  function startNew() {
    newSession();
    setHydrated(null);
    router.replace(`/workspace?tab=${active}`, { scroll: false });
  }

  if (!ready) return <ShellLoader />;

  const awaitingSession = !!sessionParam && hydrated?.sessionId !== sessionParam;

  const initial = (tab: TabKey): StoredMessage[] | undefined =>
    hydrated && hydrated.sessionId === sessionId ? hydrated.messages[tab] : undefined;

  return (
    <WorkspaceShell>

      <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6 py-6 lg:px-8">

        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <span className="eyebrow">
              <span className="h-px w-6 bg-gold-500" />
              Session
            </span>
            <h1 className="mt-1.5 line-clamp-1 font-serif text-lg font-semibold tracking-tight text-ink sm:text-xl">
              {matter || "New session"}
            </h1>
          </div>
          <button onClick={startNew} className="btn-ghost shrink-0 gap-1.5 px-3 py-2 text-xs">
            <PlusIcon /> New session
          </button>
        </div>

        <div role="tablist" aria-label="Workspace tools" className="mt-4 flex flex-wrap gap-1.5 border-b border-ink/10">
          {TABS.map((t) => {
            const Icon = t.icon;
            const on = active === t.key;
            return (
              <button
                key={t.key}
                role="tab"
                aria-selected={on}
                onClick={() => setTab(t.key)}
                className={`-mb-px flex items-center gap-2 rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-semibold transition ${
                  on
                    ? "border-gold-500 text-ink"
                    : "border-transparent text-ink/50 hover:text-ink/80"
                }`}
              >
                <Icon className={`h-4 w-4 ${on ? "text-gold-600" : "text-ink/40"}`} />
                {t.label}
              </button>
            );
          })}
        </div>

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
