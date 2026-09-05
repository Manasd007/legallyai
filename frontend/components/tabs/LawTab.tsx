"use client";

import { useEffect, useState } from "react";
import { ArrowIcon, BookIcon, ScalesIcon } from "@/components/ui";
import { BrandLoader } from "@/components/BrandLoader";
import { useSession } from "@/components/session";
import { FadeUp } from "@/components/motion";
import { CopyButton } from "@/components/CopyButton";
import { postJson } from "@/components/api";
import { TabIntro } from "@/components/tabs/TabIntro";
import type { StoredMessage } from "@/components/tabs/types";

type Statute = { act: string; section: string; what_it_governs: string; relevance: string };
type Related = {
  case_name: string;
  citation: string;
  court: string;
  year: number | null;
  outcome: string;
  similarity: number;
};
type Result = {
  situation_summary: string;
  statutes: Statute[];
  note: string;
  related_cases: Related[];
  weak_retrieval: boolean;
};

const EXAMPLES = [
  "A cheque I received bounced due to insufficient funds.",
  "My landlord won't return my security deposit after I vacated.",
  "I was arrested and want to apply for anticipatory bail.",
  "A company failed to deliver goods I paid for in advance.",
];

function hydrate(messages: StoredMessage[]): { question: string; res: Result | null } {
  let question = "";
  let res: Result | null = null;
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === "assistant" && m.payload && Array.isArray(m.payload.statutes)) {
      res = m.payload as Result;

      const prev = messages[i - 1];
      if (prev?.role === "user") question = prev.content;
    }
  }
  return { question, res };
}

export function LawTab({ initialMessages }: { initialMessages?: StoredMessage[] }) {
  const { matter, setSituation, attach, commitConv } = useSession();
  const seed = initialMessages ? hydrate(initialMessages) : { question: "", res: null };
  const [question, setQuestion] = useState(seed.question);
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<Result | null>(seed.res);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (matter && question.trim() === "" && !res) setQuestion(matter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matter]);

  async function submit() {
    if (!question.trim()) return;
    setSituation(question);
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      const data = await postJson<Result & { conversation_id?: string }>(
        "/api/statutes",
        attach("statutes", { question }),
      );
      commitConv("statutes", data.conversation_id);
      setRes(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const inputCard = (
    <div className="card p-0">
      <textarea
        className="w-full resize-none rounded-t-lg border-0 bg-transparent p-5 text-sm leading-relaxed text-ink outline-none placeholder:text-ink/40"
        rows={2}
        placeholder="e.g. A cheque I received for Rs 5 lakh bounced due to insufficient funds…"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <div className="flex items-center justify-end gap-3 border-t-2 border-ink/15 px-5 py-3">
        <button className="btn-primary" onClick={submit} disabled={loading || !question.trim()}>
          {loading ? "Finding…" : "Find the law"}
          {!loading && <ArrowIcon />}
        </button>
      </div>
    </div>
  );

  if (!res && !loading) {
    return (
      <TabIntro
        icon={BookIcon}
        title="Find the law"
        subtitle="Describe your situation and we'll point you to the Indian laws that apply, what each one means, and the Supreme Court cases behind them."
        composer={inputCard}
        notice={
          error ? (
            <p className="mt-4 rounded border-2 border-red-400 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          ) : undefined
        }
        examples={EXAMPLES.map((ex) => ({ label: ex, onClick: () => setQuestion(ex) }))}
      />
    );
  }

  return (
    <div className="w-full">
      {inputCard}

      {loading && (
        <div className="mt-8 card flex justify-center py-14">
          <BrandLoader label="Finding the law…" sub="Identifying the governing Acts and sections" />
        </div>
      )}

      {res && (
        <FadeUp className="mt-8 space-y-5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-ink/45">
              {res.statutes.length} law{res.statutes.length === 1 ? "" : "s"} that may apply
            </span>
            {res.statutes.length > 0 && (
              <CopyButton
                label="Copy statutes"
                text={[
                  res.situation_summary,
                  ...res.statutes.map(
                    (s) => `${s.act}${s.section ? `, ${s.section}` : ""}\n  ${s.what_it_governs}`,
                  ),
                ].join("\n")}
              />
            )}
          </div>
          {res.situation_summary && (
            <div className="card">
              <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-ink/50">
                In short
              </div>
              <p className="mt-2 text-sm leading-relaxed text-ink/75">{res.situation_summary}</p>
            </div>
          )}

          {res.statutes.length > 0 ? (
            <div className="space-y-3">
              {res.statutes.map((s, i) => (
                <div key={i} className="card">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded border-2 border-ink bg-navy-900 text-gold-400 shadow-brutal-sm">
                      <BookIcon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <span className="font-serif text-lg font-semibold text-ink">{s.act}</span>
                        {s.section && (
                          <span className="rounded border-2 border-gold-500/40 bg-gold-400/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-gold-700">
                            {s.section}
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-ink/75">{s.what_it_governs}</p>
                      {s.relevance && (
                        <p className="mt-2 border-l-2 border-gold-400 pl-3 text-sm text-ink/65">
                          <span className="font-medium text-ink/80">Why it applies:</span> {s.relevance}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card text-sm text-ink/70">
              We couldn&apos;t pin down a clear law for this from the cases we matched. Try adding
              more detail about what happened, the more specific you are, the better.
            </div>
          )}

          {res.note && (
            <p className="rounded border-2 border-ink/15 bg-ink/[0.04] p-3 text-xs leading-relaxed text-ink/60">{res.note}</p>
          )}

          {res.related_cases.length > 0 && (
            <div className="card">
              <h2 className="flex items-center gap-2 font-serif text-lg font-semibold text-ink">
                <ScalesIcon className="h-5 w-5 text-gold-600" /> Real cases that used these laws
              </h2>
              <ul className="mt-3 space-y-2">
                {res.related_cases.map((c, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-3 rounded border-2 border-ink/20 bg-surface/50 px-4 py-2.5 text-sm backdrop-blur-sm transition hover:border-ink"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium text-ink">{c.case_name}</div>
                      <div className="text-xs text-ink/50">{c.citation || `${c.court} ${c.year ?? ""}`}</div>
                    </div>
                    <span className="shrink-0 text-xs tabular-nums text-ink/45">
                      {Math.round(c.similarity * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </FadeUp>
      )}
    </div>
  );
}
