"use client";

import { useState } from "react";
import { CaseModal } from "@/components/CaseModal";

type Source = {
 court?: string;
 year?: number | null;
 outcome?: string;
 segment_role?: string;
 excerpt?: string;
 similarity?: number;
 chunk_id?: string;
};

export type CaseLike = {
 case_name: string;
 citation?: string;
 relevance?: string;
 court?: string;
 year?: number | null;
 outcome?: string;
 similarity?: number;
 segment_role?: string;
 excerpt?: string;
 chunk_id?: string;
 source?: Source;
};

function outcomeTone(outcome?: string): string {
 const o = (outcome || "").toLowerCase();
 if (o.includes("allow") || o.includes("grant")) return "bg-emerald-500/10 text-emerald-700";
 if (o.includes("dismiss") || o.includes("reject")) return "bg-red-500/10 text-red-600";
 return "bg-ink/5 text-ink/60";
}

export function CitedCase({ c }: { c: CaseLike }) {
 const [open, setOpen] = useState(false);
 const [showFull, setShowFull] = useState(false);
 const src: Source = c.source ?? c;
 const excerpt = src.excerpt;
 const sim = c.source?.similarity ?? c.similarity;
 const role = src.segment_role;
 const outcome = src.outcome;
 const sub = c.citation || [src.court, src.year].filter(Boolean).join(" ");
 const highlightId = c.source?.chunk_id ?? c.chunk_id;

 return (
 <div className="rounded-xl border border-ink/10 bg-surface/60">
 {showFull && (
 <CaseModal
 citation={c.citation}
 caseName={c.case_name}
 highlightId={highlightId}
 onClose={() => setShowFull(false)}
 />
 )}
 <button
 onClick={() => setShowFull(true)}
 title="Open the full judgment with the cited passage highlighted"
 className="group flex w-full items-start justify-between gap-3 rounded-t-xl px-4 py-3 text-left transition hover:bg-ink/[0.03]"
 >
 <div className="min-w-0">
 <div className="flex items-center gap-1.5">
 <CheckBadge />
 <span className="truncate text-sm font-semibold text-ink underline-offset-2 group-hover:underline">
 {c.case_name}
 </span>
 </div>
 {sub && <div className="mt-0.5 pl-5 text-xs text-ink/50">{sub}</div>}
 {c.relevance && <div className="mt-1.5 pl-5 text-xs leading-relaxed text-ink/70">{c.relevance}</div>}
 <div className="mt-1.5 pl-5 text-[11px] font-medium text-gold-700 opacity-80 group-hover:opacity-100">
 Click to read the full judgment →
 </div>
 </div>
 <div className="flex shrink-0 items-center gap-2">
 {typeof sim === "number" && (
 <span className="text-xs tabular-nums text-ink/45">{Math.round(sim * 100)}%</span>
 )}
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
 strokeLinecap="round" strokeLinejoin="round"
 className="h-4 w-4 text-ink/30 transition group-hover:text-gold-600" aria-hidden>
 <path d="M7 17L17 7M8 7h9v9" />
 </svg>
 </div>
 </button>

 {excerpt && (
 <div className="border-t border-ink/10 px-4 py-2">
 <button
 onClick={() => setOpen((v) => !v)}
 className="inline-flex items-center gap-1 text-xs font-medium text-gold-700 transition hover:text-gold-600"
 >
 {open ? "Hide quick preview" : "Quick preview of cited passage"}
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
 strokeLinecap="round" strokeLinejoin="round"
 className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden>
 <path d="M6 9l6 6 6-6" />
 </svg>
 </button>

 {open && (
 <div className="mt-2 space-y-2">
 <div className="flex flex-wrap items-center gap-2">
 {role && (
 <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] font-medium text-ink/60">
 {role}
 </span>
 )}
 {outcome && (
 <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${outcomeTone(outcome)}`}>
 {outcome}
 </span>
 )}
 </div>
 <blockquote className="max-h-48 overflow-auto rounded-lg border-l-2 border-gold-400 bg-ink/[0.03] px-3 py-2 text-xs leading-relaxed text-ink/70">
 “{excerpt}”
 </blockquote>
 <p className="text-[11px] text-ink/40">
 Verbatim from the indexed judgment, or open the full case to see it in context.
 </p>
 </div>
 )}
 </div>
 )}
 </div>
 );
}

function CheckBadge() {
 return (
 <span
 title="Verified, found in the corpus"
 className="grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full bg-emerald-500/15 text-emerald-600"
 >
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
 strokeLinecap="round" strokeLinejoin="round" className="h-2.5 w-2.5" aria-hidden>
 <path d="M20 6L9 17l-5-5" />
 </svg>
 </span>
 );
}

export function TrustBadge({ verified, fabricated }: { verified: number; fabricated: number }) {
 const clean = fabricated === 0;
 return (
 <div
 className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
 clean
 ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
 : "border-gold-500/30 bg-gold-400/10 text-gold-700"
 }`}
 >
 <CheckBadge />
 {verified} citation{verified === 1 ? "" : "s"} verified against the corpus
 {fabricated > 0 ? ` · ${fabricated} unverified removed` : " · 0 fabricated"}
 </div>
 );
}
