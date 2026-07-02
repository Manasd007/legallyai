"use client";

/* Browser-side Supabase client (auth only — the corpus and predictions live
   behind the FastAPI backend, not direct Postgres). One shared instance per tab;
   it persists the session to localStorage and refreshes tokens automatically.

   If the env vars are missing (e.g. a contributor hasn't set up Supabase yet),
   `supabase` is null and the app runs in "signed-out / dev" mode rather than
   crashing — auth simply isn't available. */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabaseEnabled = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = supabaseEnabled
  ? createClient(url as string, anonKey as string, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

/** The current access token (JWT), or null when signed out / Supabase off. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
