"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth";
import { useSession } from "@/components/session";
import { getJson } from "@/components/api";
import { ScalesIcon, ChatIcon, BookIcon, DocIcon } from "@/components/ui";

/* The signed-in account control + the list of past sessions. Both live in the
   workspace sidebar. History only loads when a user is signed in — otherwise
   sessions aren't saved to an account. */

type SessionItem = {
  session_id: string;
  title: string | null;
  updated_at: string;
  tools: string[];
  conversation_count: number;
};

const TOOL_META: Record<string, { icon: typeof ScalesIcon; label: string }> = {
  predict: { icon: ScalesIcon, label: "Case" },
  assistant: { icon: ChatIcon, label: "Question" },
  statutes: { icon: BookIcon, label: "Statutes" },
  documents: { icon: DocIcon, label: "Document" },
};

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function AccountPanel({ onNavigate }: { onNavigate?: () => void }) {
  const { user, ready, enabled, signInWithEmail, signInWithGoogle, signOut } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!enabled) {
    return (
      <div className="rounded-xl border border-dashed border-ink/15 bg-surface/40 p-3 text-[11px] leading-relaxed text-ink/50">
        Sign-in isn’t configured. Set the Supabase keys to save your history across visits.
      </div>
    );
  }

  if (!ready) return <div className="h-12 animate-pulse rounded-xl bg-ink/5" />;

  if (user) {
    return (
      <div className="rounded-xl border border-ink/10 bg-surface/50 p-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-navy-900 text-xs font-semibold text-cream">
            {(user.email?.[0] || "U").toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold text-ink/80">{user.email || "Signed in"}</span>
            <button onClick={signOut} className="text-[11px] font-medium text-ink/45 transition hover:text-ink/80">
              Sign out
            </button>
          </span>
        </div>
      </div>
    );
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await signInWithEmail(email);
      setSent(true);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Couldn't send the link.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="rounded-xl border border-gold-500/30 bg-gold-400/[0.07] p-3 text-[11px] leading-relaxed text-ink/70">
        Check <span className="font-semibold">{email}</span> for a sign-in link. Open it on this device to continue.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-ink/10 bg-surface/50 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink/45">Save your history</div>
      <form onSubmit={send} className="mt-2 flex flex-col gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@email.com"
          className="rounded-lg border border-ink/15 bg-parchment/60 px-2.5 py-1.5 text-xs text-ink outline-none placeholder:text-ink/40 focus:border-ink/30"
        />
        <button type="submit" disabled={busy || !email.trim()} className="btn-primary justify-center px-3 py-1.5 text-xs">
          {busy ? "Sending…" : "Email me a link"}
        </button>
      </form>
      <button
        onClick={() => signInWithGoogle().catch((e) => setErr(e.message))}
        className="mt-2 w-full rounded-lg border border-ink/15 bg-parchment/60 px-3 py-1.5 text-xs font-medium text-ink/75 transition hover:border-ink/30"
      >
        Continue with Google
      </button>
      {err && <p className="mt-1.5 text-[11px] text-red-600/80">{err}</p>}
    </div>
  );
}

export function HistoryPanel({ onNavigate }: { onNavigate?: () => void }) {
  const { user, ready } = useAuth();
  const { sessionId } = useSession();
  const pathname = usePathname();
  const [items, setItems] = useState<SessionItem[] | null>(null);

  const load = useCallback(() => {
    if (!user) {
      setItems(null);
      return;
    }
    getJson<{ sessions: SessionItem[] }>("/api/sessions")
      .then((d) => setItems(d.sessions || []))
      .catch(() => setItems([]));
  }, [user]);

  // Reload on sign-in, on navigation (a new session may have just been created),
  // and when the tab regains focus.
  useEffect(() => {
    load();
  }, [load, pathname]);
  useEffect(() => {
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  if (!ready || !user) return null;

  // Order the tool chips consistently (Assess · Ask · Find law) and de-duplicate.
  const TOOL_ORDER = ["predict", "documents", "assistant", "statutes"];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink/40">History</div>
      {items === null ? (
        <div className="space-y-1.5 px-1">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded-lg bg-ink/5" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="px-2 text-[11px] leading-relaxed text-ink/45">
          Your past sessions will appear here. Ask a question or assess a case to start one.
        </p>
      ) : (
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1">
          {items.map((s) => {
            const active = s.session_id === sessionId;
            const tools = [...s.tools].sort((a, b) => TOOL_ORDER.indexOf(a) - TOOL_ORDER.indexOf(b));
            return (
              <Link
                key={s.session_id}
                href={`/workspace?session=${s.session_id}`}
                onClick={onNavigate}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 transition ${
                  active ? "bg-ink/10" : "hover:bg-ink/5"
                }`}
              >
                <span className="flex shrink-0 -space-x-1.5">
                  {tools.map((t) => {
                    const Icon = (TOOL_META[t] || TOOL_META.assistant).icon;
                    return (
                      <span
                        key={t}
                        className="grid h-6 w-6 place-items-center rounded-full bg-surface text-ink/55 ring-1 ring-ink/10"
                      >
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                    );
                  })}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-medium text-ink/80">
                    {s.title || "Session"}
                  </span>
                  <span className="block text-[11px] text-ink/45">{timeAgo(s.updated_at)}</span>
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
