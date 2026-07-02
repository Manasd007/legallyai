"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { supabase, supabaseEnabled } from "@/lib/supabase";

/* Auth state for the whole app. Wraps Supabase Auth so components just read
   `useAuth()` — they never touch the client directly. When Supabase isn't
   configured the app still works signed-out (history simply isn't saved). */

type AuthUser = { id: string; email: string | null };

/* Build an absolute redirect URL from a path like "/predict". Supabase needs an
   absolute URL, and it must be in the project's allowed Redirect URLs list. */
function resolveRedirect(redirectTo?: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  if (!redirectTo) return window.location.origin;
  return redirectTo.startsWith("http") ? redirectTo : `${window.location.origin}${redirectTo}`;
}

type Ctx = {
  user: AuthUser | null;
  /** True until we've checked for an existing session (avoids a flash). */
  ready: boolean;
  /** Whether Supabase is configured at all. */
  enabled: boolean;
  /** Email magic-link sign-in. `redirectTo` is where the link lands them. */
  signInWithEmail: (email: string, redirectTo?: string) => Promise<void>;
  signInWithGoogle: (redirectTo?: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!supabase) {
      setReady(true);
      return;
    }
    // Read any persisted session, then subscribe to future changes.
    supabase.auth.getSession().then(({ data }) => {
      const u = data.session?.user;
      setUser(u ? { id: u.id, email: u.email ?? null } : null);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user;
      setUser(u ? { id: u.id, email: u.email ?? null } : null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signInWithEmail = useCallback(async (email: string, redirectTo?: string) => {
    if (!supabase) throw new Error("Sign-in isn't configured yet.");
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: resolveRedirect(redirectTo) },
    });
    if (error) throw new Error(error.message);
  }, []);

  const signInWithGoogle = useCallback(async (redirectTo?: string) => {
    if (!supabase) throw new Error("Sign-in isn't configured yet.");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: resolveRedirect(redirectTo) },
    });
    if (error) throw new Error(error.message);
  }, []);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, ready, enabled: supabaseEnabled, signInWithEmail, signInWithGoogle, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
