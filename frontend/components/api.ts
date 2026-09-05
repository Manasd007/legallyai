
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
