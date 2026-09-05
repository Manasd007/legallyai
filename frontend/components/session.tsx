"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";




const KEY = "legally.session.v1";

export type Tool = "predict" | "assistant" | "statutes";

type Persisted = {
  sessionId: string;
  matter: string | null;
  conv: Partial<Record<Tool, string>>;
};

type Ctx = {
  sessionId: string;
  matter: string | null;
  ready: boolean;
  setSituation: (text: string) => void;
  convId: (tool: Tool) => string | null;
  commitConv: (tool: Tool, id: string | null | undefined) => void;
  resetConv: (tool: Tool) => void;
  attach: <T extends object>(
    tool: Tool,
    body: T,
  ) => T & { conversation_id: string | null; session_id: string };
  newSession: () => void;
  loadSession: (sessionId: string, conv: Partial<Record<Tool, string>>, matter: string | null) => void;
};

const SessionContext = createContext<Ctx | null>(null);

function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
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
