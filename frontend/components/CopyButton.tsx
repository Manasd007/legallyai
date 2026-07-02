"use client";

import { useState } from "react";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
 const [copied, setCopied] = useState(false);

 async function copy() {
 try {
 await navigator.clipboard.writeText(text);
 setCopied(true);
 setTimeout(() => setCopied(false), 1500);
 } catch {
 /* clipboard blocked, ignore */
 }
 }

 return (
 <button
 onClick={copy}
 className="inline-flex items-center gap-1.5 rounded-lg border border-ink/15 bg-surface/60 px-3 py-1.5 text-xs font-medium text-ink/70 transition hover:border-ink/30 hover:text-ink"
 >
 {copied ? (
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
 strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 text-emerald-600" aria-hidden>
 <path d="M20 6L9 17l-5-5" />
 </svg>
 ) : (
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
 strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
 <rect x="9" y="9" width="11" height="11" rx="2" />
 <path d="M5 15V5a2 2 0 0 1 2-2h10" />
 </svg>
 )}
 {copied ? "Copied" : label}
 </button>
 );
}
