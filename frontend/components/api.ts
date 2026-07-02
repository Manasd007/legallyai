/* Resilient JSON POST helper.

 The backend (and the dev proxy in front of it) can return a non-JSON body on
 errors, e.g. a plain "Internal Server Error" during a cold start or a proxy
 timeout. Calling `res.json()` on those throws a cryptic
 "Unexpected token 'I' … is not valid JSON". This helper reads the body once,
 parses it defensively, and raises a clean, user-facing message instead. */
/* Read a Response body once and parse it as JSON, tolerating non-JSON error
 bodies (proxy timeouts, plain-text 500s). Throws a clean message on failure. */
export async function readJsonResponse<T = any>(res: Response): Promise<T> {
 const raw = await res.text();
 let data: any = null;
 if (raw) {
 try {
 data = JSON.parse(raw);
 } catch {
 /* Non-JSON body (proxy/error page), handled below. */
 }
 }

 if (!res.ok) {
 const detail =
 (data && (data.detail || data.message)) ||
 `The server returned an error (HTTP ${res.status}). Please try again.`;
 throw new Error(detail);
 }

 return data as T;
}

import { getAccessToken } from "@/lib/supabase";

/* Attach the signed-in user's Supabase token so the backend can scope the
 request to their account (per-user history). Signed out → no header, and the
 backend treats it as the local "dev-user". Exported so the few callers that use
 raw fetch (e.g. multipart file upload) can opt in too. */
export async function authHeaders(): Promise<Record<string, string>> {
 const token = await getAccessToken();
 return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function postJson<T = any>(url: string, body: unknown): Promise<T> {
 let res: Response;
 try {
 res = await fetch(url, {
 method: "POST",
 headers: { "Content-Type": "application/json", ...(await authHeaders()) },
 body: JSON.stringify(body),
 });
 } catch {
 throw new Error(
 "Couldn't reach the server. Check that the backend is running and try again.");
 }
 return readJsonResponse<T>(res);
}

export async function getJson<T = any>(url: string): Promise<T> {
 let res: Response;
 try {
 res = await fetch(url, { headers: { ...(await authHeaders()) } });
 } catch {
 throw new Error(
 "Couldn't reach the server. Check that the backend is running and try again.");
 }
 return readJsonResponse<T>(res);
}
