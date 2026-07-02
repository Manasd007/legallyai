"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

/* The workspace "session" — one matter, worked across three tabs that share it.
   A session bundles up to three per-tool backend threads under a single
   client-generated `sessionId`, so a matter shows in history as ONE entry.

   - `matter`     the user's situation text, described once and reused by every tab.
   - `sessionId`  the shared id stamped on every request; groups the threads.
   - per-tool `conversationId`  keeps each tab's own thread going across turns.

   Persisted to localStorage so a refresh stays in the same session. Replaces the
   older matter-only context. */

const KEY = "legally.session.v1";

export type Tool = "predict" | "assistant" | "statutes";

type Persisted = {
  sessionId: string;
  matter: string | null;
  conv: Partial<Record<Tool, string>>;
};

type Ctx = {
  /** Current session id, stamped on every request. */
  sessionId: string;
  /** The shared situation text, or null until described. */
  matter: string | null;
  /** True once localStorage has been read (avoids a flash). */
  ready: boolean;
  /** Record the matter from a situation description (first non-empty wins). */
  setSituation: (text: string) => void;
  /** The backend thread id for one tool, if it has started. */
  convId: (tool: Tool) => string | null;
  /** Capture the thread id the backend echoed for a tool. */
  commitConv: (tool: Tool, id: string | null | undefined) => void;
  /** Forget one tool's thread so its next turn starts fresh (within this session). */
  resetConv: (tool: Tool) => void;
  /** Add `conversation_id` (per tool) + `session_id` to a request body. */
  attach: <T extends object>(
    tool: Tool,
    body: T,
  ) => T & { conversation_id: string | null; session_id: string };
  /** Start a fresh session: new id, no matter, no threads. */
  newSession: () => void;
  /** Switch to an existing session (e.g. opened from history) and seed its threads. */
  loadSession: (sessionId: string, conv: Partial<Record<Tool, string>>, matter: string | null) => void;
};

const SessionContext = createContext<Ctx | null>(null);

function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    // Fallback for older browsers / non-secure contexts.
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Persisted>({ sessionId: "", matter: null, conv: {} });
  const [ready, setReady] = useState(false);
  const loaded = useRef(false);

  // Read (or initialise) the persisted session once on mount.
  useEffect(() => {
    let next: Persisted | null = null;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) next = JSON.parse(raw) as Persisted;
    } catch {
      /* ignore corrupt/unavailable storage */
    }
    if (!next || !next.sessionId) {
      next = { sessionId: newId(), matter: null, conv: {} };
    }
    setState(next);
    loaded.current = true;
    setReady(true);
  }, []);

  // Persist on every change, but only after the initial read.
  useEffect(() => {
    if (!loaded.current) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [state]);

  const setSituation = useCallback((text: string) => {
    const situation = text.trim();
    if (!situation) return;
    setState((s) => (s.matter ? s : { ...s, matter: situation }));
  }, []);

  const convId = useCallback(
    (tool: Tool) => state.conv[tool] ?? null,
    [state.conv],
  );

  const commitConv = useCallback((tool: Tool, id: string | null | undefined) => {
    if (!id) return;
    setState((s) => (s.conv[tool] === id ? s : { ...s, conv: { ...s.conv, [tool]: id } }));
  }, []);

  const resetConv = useCallback((tool: Tool) => {
    setState((s) => {
      if (!(tool in s.conv)) return s;
      const conv = { ...s.conv };
      delete conv[tool];
      return { ...s, conv };
    });
  }, []);

  const attach = useCallback(
    <T extends object>(tool: Tool, body: T) => ({
      ...body,
      conversation_id: state.conv[tool] ?? null,
      session_id: state.sessionId,
    }),
    [state.conv, state.sessionId],
  );

  const newSession = useCallback(() => {
    setState({ sessionId: newId(), matter: null, conv: {} });
  }, []);

  const loadSession = useCallback(
    (sessionId: string, conv: Partial<Record<Tool, string>>, matter: string | null) => {
      setState({ sessionId, conv, matter });
    },
    [],
  );

  return (
    <SessionContext.Provider
      value={{
        sessionId: state.sessionId,
        matter: state.matter,
        ready,
        setSituation,
        convId,
        commitConv,
        resetConv,
        attach,
        newSession,
        loadSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within <SessionProvider>");
  return ctx;
}
