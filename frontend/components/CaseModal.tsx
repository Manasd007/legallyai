"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useScrollLock } from "@/components/scrollLock";

type Chunk = { text: string; role: string; cited: boolean };
type CaseDoc = {
  case_name: string;
  citation: string;
  court: string;
  year: number | null;
  outcome: string;
  n_chunks: number;
  chunks: Chunk[];
};

export function CaseModal({
  citation,
  caseName,
  highlightId,
  onClose,
}: {
  citation?: string;
  caseName?: string;
  highlightId?: string;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<CaseDoc | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const citedRef = useRef<HTMLDivElement>(null);

  // Render through a portal on the client only (document isn't available on the
  // server). The portal is essential: cited-case cards animate via framer-motion,
  // and a transformed ancestor would otherwise trap our `position: fixed` overlay.
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const r = await fetch("/api/case", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            citation: citation || "",
            case_name: caseName || "",
            highlight_id: highlightId || "",
          }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d?.detail || "Could not load the case.");
        if (active) setDoc(d);
      } catch (e) {
        if (active) setErr(e instanceof Error ? e.message : "Failed to load.");
      }
    })();
    return () => {
      active = false;
    };
  }, [citation, caseName, highlightId]);

  // Stop the page (and Lenis) from scrolling behind the modal.
  useScrollLock(true);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (doc) {
      const t = setTimeout(() => citedRef.current?.scrollIntoView({ block: "center" }), 120);
      return () => clearTimeout(t);
    }
  }, [doc]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/60 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl bg-surface shadow-lift sm:max-h-[88vh] sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-ink/10 bg-surface px-5 py-4">
          <div className="min-w-0">
            <div className="font-serif text-base font-semibold leading-snug text-ink">
              {doc?.case_name || caseName || "Judgment"}
            </div>
            <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-ink/50">
              {[doc?.citation || citation, doc?.court, doc?.year].filter(Boolean).join(" · ")}
              {doc?.outcome ? ` · ${doc.outcome}` : ""}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-lg p-1.5 text-ink/50 transition hover:bg-ink/5 hover:text-ink"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
              strokeLinecap="round" className="h-5 w-5" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-auto px-5 py-5 sm:px-6" data-lenis-prevent>
          {err && <p className="text-sm text-red-600">{err}</p>}
          {!doc && !err && (
            <div className="flex items-center gap-2 py-8 text-sm text-ink/55">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink/20 border-t-gold-500" />
              Loading the full judgment…
            </div>
          )}
          {doc && (
            <div className="mx-auto max-w-2xl">
              <p className="mb-5 rounded-lg border border-ink/10 bg-ink/[0.03] px-3.5 py-2.5 font-mono text-[11px] leading-relaxed text-ink/55">
                Full judgment reconstructed from the indexed corpus · {doc.n_chunks} passage
                {doc.n_chunks === 1 ? "" : "s"}. The{" "}
                <span className="font-semibold text-gold-700">highlighted passage</span> is the one
                the answer relied on.
              </p>

              <div className="space-y-1">
                {doc.chunks.map((ch, i) => (
                  <div
                    key={i}
                    ref={ch.cited ? citedRef : undefined}
                    className={
                      ch.cited
                        ? "scroll-mt-4 my-3 rounded-lg border-l-4 border-gold-500 bg-gold-400/10 px-4 py-3.5"
                        : "px-1 py-2"
                    }
                  >
                    {ch.cited ? (
                      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-gold-700">
                        ▸ Passage the answer relied on
                      </div>
                    ) : (
                      ch.role && (
                        <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-ink/35">
                          {ch.role}
                        </div>
                      )
                    )}
                    <p
                      className={`whitespace-pre-wrap font-mono text-[13px] leading-[1.75] ${
                        ch.cited ? "text-ink/90" : "text-ink/70"
                      }`}
                    >
                      {ch.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
