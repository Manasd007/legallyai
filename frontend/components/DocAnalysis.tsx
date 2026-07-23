"use client";

import { useState } from "react";
import { DocIcon, ShieldCheckIcon } from "@/components/ui";
import { BrandLoader } from "@/components/BrandLoader";
import { postJson } from "@/components/api";

export type Party = { name: string; role: string };
export type KeyDate = { label: string; date: string };
export type KeyPoint = { heading: string; detail: string };
export type Deadline = { action: string; due: string; urgency: "critical" | "important" | "routine" };
export type Amount = { label: string; amount: string };
export type Option = { option: string; detail: string };
export type Term = { term: string; definition: string };
export type Analysis = {
  doc_id: string;
  filename: string;
  char_count: number;
  document_type: string;
  title: string;
  summary: string;
  your_position: string;
  parties: Party[];
  key_dates: KeyDate[];
  deadlines: Deadline[];
  amounts: Amount[];
  key_points: KeyPoint[];
  glossary: Term[];
  obligations: string[];
  your_options: Option[];
  recommended_actions: string[];
  risks_or_flags: string[];
  governing_law: string;
  confidence: string;
  suggested_questions: string[];
  injection_warning: string;
  truncated: boolean;
  ocr: boolean;
};

export function DocAnalysisView({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-5">
      <DocHeader analysis={analysis} />
      {analysis.injection_warning && <InjectionNotice text={analysis.injection_warning} />}
      <WhereYouStand analysis={analysis} />
      <Deadlines items={analysis.deadlines} />
      <Summary analysis={analysis} />
      <FactsGrid analysis={analysis} />
      <KeyPoints points={analysis.key_points} />
      <RecommendedActions steps={analysis.recommended_actions} />
      <YourOptions options={analysis.your_options} />
      <ObligationsRisks analysis={analysis} />
      <LegalTerms docId={analysis.doc_id} glossary={analysis.glossary} />
    </div>
  );
}

function DocHeader({ analysis }: { analysis: Analysis }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-navy-900 text-gold-400">
        <DocIcon className="h-5 w-5" />
      </span>
      <div>
        <div className="font-semibold text-ink">{analysis.title || analysis.filename}</div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink/55">
          <span>
            {analysis.document_type} · {analysis.char_count.toLocaleString()} characters
          </span>
          {analysis.ocr && (
            <span className="rounded-full bg-gold-400/15 px-2 py-0.5 font-medium text-gold-700">
              Read via OCR
            </span>
          )}
          {analysis.truncated && <span>· long document (analyzed the first portion)</span>}
        </div>
      </div>
    </div>
  );
}

function Summary({ analysis }: { analysis: Analysis }) {
  return (
    <div className="card">
      <span className="inline-flex items-center gap-2 rounded-full bg-ink/5 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-ink/60">
        {analysis.document_type}
      </span>
      <p className="mt-3 leading-relaxed text-ink/80">{analysis.summary}</p>
    </div>
  );
}

function FactsGrid({ analysis }: { analysis: Analysis }) {
  const hasParties = analysis.parties.length > 0;
  const hasDates = analysis.key_dates.length > 0;
  const hasAmounts = analysis.amounts.length > 0;
  const hasLaw = !!analysis.governing_law;
  if (!hasParties && !hasDates && !hasAmounts && !hasLaw) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {hasParties && (
        <div className="card min-w-0">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/55">Parties</h3>
          <ul className="mt-3 space-y-3">
            {analysis.parties.map((p, i) => (
              <li key={i} className="text-sm leading-snug">
                <div className="font-medium text-ink">{p.name}</div>
                {p.role && (
                  <div className="mt-0.5 text-ink/55">{p.role}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasDates && (
        <div className="card min-w-0">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/55">Key dates</h3>
          <ul className="mt-3 space-y-3">
            {analysis.key_dates.map((d, i) => (
              <li
                key={i}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 text-sm"
              >
                <span className="text-ink/70">{d.label || "Date"}</span>
                <span className="shrink-0 text-right font-medium tabular-nums text-ink">{d.date}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasAmounts && (
        <div className="card min-w-0">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/55">Amounts</h3>
          <ul className="mt-3 space-y-3">
            {analysis.amounts.map((a, i) => (
              <li
                key={i}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 text-sm"
              >
                <span className="text-ink/70">{a.label || "Amount"}</span>
                <span className="shrink-0 text-right font-semibold tabular-nums text-ink">{a.amount}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasLaw && (
        <div className={`card min-w-0 ${hasAmounts ? "" : "sm:col-span-2"}`}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/55">Governing law</h3>
          <p className="mt-3 text-sm leading-relaxed text-ink/80">{analysis.governing_law}</p>
        </div>
      )}
    </div>
  );
}

function WhereYouStand({ analysis }: { analysis: Analysis }) {
  if (!analysis.your_position) return null;
  return (
    <div className="card border border-gold-500/30 bg-gold-400/[0.06]">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-gold-700">
          Where you stand
        </span>
        {analysis.confidence && <ConfidenceTag confidence={analysis.confidence} />}
      </div>
      <p className="mt-2 font-serif text-lg leading-relaxed text-ink sm:text-xl">
        {analysis.your_position}
      </p>
    </div>
  );
}

function ConfidenceTag({ confidence }: { confidence: string }) {
  const map: Record<string, string> = {
    high: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    medium: "bg-gold-400/15 text-gold-700",
    low: "bg-ink/5 text-ink/60",
  };
  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
        map[confidence] ?? map.low
      }`}
    >
      {confidence} confidence
    </span>
  );
}

const URGENCY: Record<Deadline["urgency"], { label: string; cls: string; dot: string }> = {
  critical: { label: "Critical", cls: "border-red-500/30 bg-red-500/[0.06]", dot: "bg-red-500" },
  important: { label: "Important", cls: "border-gold-500/30 bg-gold-400/[0.07]", dot: "bg-gold-500" },
  routine: { label: "Routine", cls: "border-ink/10 bg-surface/60", dot: "bg-ink/40" },
};

function Deadlines({ items }: { items: Deadline[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card">
      <h2 className="font-serif text-lg font-semibold text-ink">Deadlines &amp; time limits</h2>
      <p className="mt-1 text-xs text-ink/55">
        Act on these in time, missing them can have legal consequences.
      </p>
      <div className="mt-4 space-y-2.5">
        {items.map((d, i) => {
          const u = URGENCY[d.urgency] ?? URGENCY.important;
          return (
            <div key={i} className={`flex items-start gap-3 rounded-xl border p-3.5 ${u.cls}`}>
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${u.dot}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{d.action}</div>
                {d.due && <div className="mt-0.5 text-xs text-ink/65">{d.due}</div>}
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                  d.urgency === "critical"
                    ? "bg-red-500/10 text-red-600"
                    : d.urgency === "routine"
                    ? "bg-ink/5 text-ink/55"
                    : "bg-gold-400/15 text-gold-700"
                }`}
              >
                {u.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecommendedActions({ steps }: { steps: string[] }) {
  if (!steps || steps.length === 0) return null;
  return (
    <div className="card border border-gold-500/30 bg-gold-400/[0.06]">
      <h2 className="font-serif text-lg font-semibold text-ink">What you should do next</h2>
      <p className="mt-1 text-xs text-ink/60">
        Practical steps based on this document, in priority order. Worth confirming with an advocate.
      </p>
      <ol className="mt-4 space-y-2.5 text-sm text-ink/80">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-gold-500/20 text-[11px] font-semibold text-gold-700">
              {i + 1}
            </span>
            <span className="leading-relaxed">{step}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function YourOptions({ options }: { options: Option[] }) {
  if (!options || options.length === 0) return null;
  return (
    <div className="card">
      <h2 className="font-serif text-lg font-semibold text-ink">Your options</h2>
      <p className="mt-1 text-xs text-ink/55">
        Routes open to you on the face of this document, things to consider, not directions.
      </p>
      <ul className="mt-4 space-y-3">
        {options.map((o, i) => (
          <li key={i} className="border-l-2 border-gold-400 pl-4">
            <div className="text-sm font-medium text-ink">{o.option}</div>
            {o.detail && <p className="mt-0.5 text-xs leading-relaxed text-ink/65">{o.detail}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InjectionNotice({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-400/40 bg-red-500/[0.06] p-4">
      <ShieldCheckIcon className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
      <div className="text-sm leading-relaxed text-ink/80">
        <span className="font-semibold text-ink">Security note. </span>
        {text}
      </div>
    </div>
  );
}

function KeyPoints({ points }: { points: KeyPoint[] }) {
  if (points.length === 0) return null;
  return (
    <div className="card">
      <h2 className="font-serif text-lg font-semibold text-ink">Key terms</h2>
      <div className="mt-4 space-y-4">
        {points.map((p, i) => (
          <div key={i} className="border-l-2 border-gold-400 pl-4">
            {p.heading && <div className="font-semibold text-ink">{p.heading}</div>}
            <p className="mt-0.5 text-sm leading-relaxed text-ink/75">{p.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ObligationsRisks({ analysis }: { analysis: Analysis }) {
  const { obligations, risks_or_flags } = analysis;
  if (obligations.length === 0 && risks_or_flags.length === 0) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {obligations.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-ink">Obligations</h3>
          <ul className="mt-3 space-y-2 text-sm text-ink/75">
            {obligations.map((o, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink/40" />
                {o}
              </li>
            ))}
          </ul>
        </div>
      )}
      {risks_or_flags.length > 0 && (
        <div className="card border-gold-500/30 bg-gold-400/[0.06]">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ShieldCheckIcon className="h-4 w-4 text-gold-600" /> Worth attention
          </h3>
          <ul className="mt-3 space-y-2 text-sm text-ink/75">
            {risks_or_flags.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold-500" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LegalTerms({ docId, glossary }: { docId: string; glossary: Term[] }) {
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<{ term: string; explanation: string } | null>(null);

  async function explain(t: string) {
    const q = t.trim();
    if (!q || loading) return;
    setLoading(true);
    setAnswer(null);
    try {
      const d = await postJson<{ term: string; explanation: string }>("/api/doc/term", {
        doc_id: docId,
        term: q,
      });
      setAnswer(d);
    } catch (e) {
      setAnswer({ term: q, explanation: e instanceof Error ? e.message : "Couldn't explain that." });
    } finally {
      setLoading(false);
    }
  }

  if (glossary.length === 0) return null;

  return (
    <div className="card">
      <h2 className="font-serif text-lg font-semibold text-ink">Legal terms, explained</h2>
      <p className="mt-1 text-xs text-ink/55">
        Legal papers are full of jargon. Tap a term, or ask about any word in the document.
      </p>

      <dl className="mt-4 space-y-3">
        {glossary.map((g, i) => (
          <div key={i} className="border-l-2 border-gold-400 pl-4">
            <dt>
              <button
                onClick={() => explain(g.term)}
                className="text-sm font-semibold text-ink underline decoration-gold-400/50 decoration-dotted underline-offset-4 transition hover:decoration-gold-500"
                title={`Explain "${g.term}" in more depth`}
              >
                {g.term}
              </button>
            </dt>
            {g.definition && (
              <dd className="mt-0.5 text-xs leading-relaxed text-ink/65">{g.definition}</dd>
            )}
          </div>
        ))}
      </dl>

      {loading && (
        <div className="mt-4 flex justify-center py-2">
          <BrandLoader label="Looking it up…" size="sm" />
        </div>
      )}

      {answer && !loading && (
        <div className="mt-4 rounded-xl border border-gold-500/30 bg-gold-400/[0.06] p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-gold-700">
            {answer.term}
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-ink/80">{answer.explanation}</p>
        </div>
      )}
    </div>
  );
}
