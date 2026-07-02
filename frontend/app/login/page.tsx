"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Logo } from "@/components/ui";
import { BrandLoader } from "@/components/BrandLoader";
import { useAuth } from "@/components/auth";

/* Standalone auth screen. The workspace redirects here when a signed-out user
   tries to open a tool; `?next=` carries where they were headed so we send them
   straight back after sign-in. NOT wrapped in WorkspaceShell (that would loop
   the auth guard). */

function safeNext(raw: string | null): string {
  // Only allow same-app paths (avoid open-redirects to other sites).
  if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return "/workspace";
}

export default function Login() {
  const { user, ready, enabled, signInWithEmail, signInWithGoogle } = useAuth();
  const router = useRouter();

  const [next, setNext] = useState("/workspace");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNext(safeNext(params.get("next")));
  }, []);

  // Already signed in (or just completed the magic link) → go to the workspace.
  useEffect(() => {
    if (ready && user) router.replace(next);
  }, [ready, user, next, router]);

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await signInWithEmail(email, next);
      setSent(true);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Couldn't send the link.");
    } finally {
      setBusy(false);
    }
  }

  // While we check the session (or while redirecting a signed-in user), show a loader.
  if (!ready || user) {
    return (
      <main className="grid min-h-screen place-items-center">
        <BrandLoader />
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center">
          {/* Logo renders its own link to "/", so don't wrap it in another. */}
          <Logo withText textClassName="text-3xl" />
        </div>

        <div className="card mt-8 p-7">
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink">Sign in to continue</h1>
          <p className="mt-2 text-sm text-ink/60">
            Sign in to assess cases and keep your sessions saved across visits.
          </p>

          {!enabled ? (
            <div className="mt-6 rounded-xl border border-dashed border-ink/15 bg-surface/40 p-4 text-sm text-ink/60">
              Sign-in isn’t configured yet. Add your Supabase keys to enable accounts.
            </div>
          ) : sent ? (
            <div className="mt-6 rounded-xl border border-gold-500/30 bg-gold-400/[0.07] p-4 text-sm leading-relaxed text-ink/75">
              We sent a sign-in link to <span className="font-semibold">{email}</span>. Open it on this
              device and you’ll be taken straight to your workspace.
            </div>
          ) : (
            <>
              <form onSubmit={sendLink} className="mt-6 flex flex-col gap-3">
                <label className="text-xs font-semibold uppercase tracking-wider text-ink/45">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  autoFocus
                  className="rounded-xl border border-ink/15 bg-parchment/60 px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-ink/40 focus:border-ink/30"
                />
                <button type="submit" disabled={busy || !email.trim()} className="btn-primary justify-center px-4 py-2.5 text-sm">
                  {busy ? "Sending…" : "Email me a sign-in link"}
                </button>
              </form>

              <div className="my-4 flex items-center gap-3 text-[11px] uppercase tracking-wider text-ink/35">
                <span className="h-px flex-1 bg-ink/10" /> or <span className="h-px flex-1 bg-ink/10" />
              </div>

              <button
                onClick={() => signInWithGoogle(next).catch((e) => setErr(e.message))}
                className="w-full rounded-xl border border-ink/15 bg-parchment/60 px-4 py-2.5 text-sm font-medium text-ink/80 transition hover:border-ink/30"
              >
                Continue with Google
              </button>

              {err && <p className="mt-3 text-xs text-red-600/80">{err}</p>}
            </>
          )}
        </div>

        <p className="mt-5 text-center text-xs text-ink/45">
          <Link href="/" className="hover:text-ink/70">← Back to home</Link>
        </p>
      </div>
    </main>
  );
}
