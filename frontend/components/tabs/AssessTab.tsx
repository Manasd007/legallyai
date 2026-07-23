"use client";

import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { ArrowIcon, ScalesIcon, DocIcon } from "@/components/ui";
import { useSession } from "@/components/session";
import { useVoiceSession, voiceEnabled, type CallResult } from "@/components/voice/useVoiceSession";
import { VoiceBar } from "@/components/voice/VoiceBar";
import { LiveTurns } from "@/components/voice/LiveTurns";
import { VoiceSummary } from "@/components/VoiceSummary";
import { FadeUp, MotionBar } from "@/components/motion";
import { CopyButton } from "@/components/CopyButton";
import { CitedCase as CitedCaseCard, TrustBadge } from "@/components/CitedCase";
import { postJson, readJsonResponse, authHeaders } from "@/components/api";
import { DocAnalysisView, type Analysis } from "@/components/DocAnalysis";
import type { StoredMessage } from "@/components/tabs/types";

type Source = {
  court?: string;
  year?: number | null;
  outcome?: string;
  segment_role?: string;
  excerpt?: string;
  similarity?: number;
};
type CitedCase = { case_name: string; citation: string; relevance: string; source?: Source };
type Verification = {
  verified_count: number;
  fabricated_count: number;
  max_similarity: number;
  weak_retrieval: boolean;
};
type Factor = { factor: string; assessment: "favorable" | "unfavorable" | "unclear"; reason: string };
type PrecedentCase = {
  case_name: string;
  citation: string;
  outcome: string;
  label: number;
  similarity: number;
};
type Signals = {
  precedent_vote?: {
    applicable: boolean;
    win_probability: number | null;
    n_cases: number;
    won: number;
    lost: number;
    cases?: PrecedentCase[];
  };
  llm_forecast?: { likely_outcome: string; label: number | null };
  classifier?: { available: boolean; win_probability: number | null };
  agreement?: string;
  confidence?: string;
  signals_used?: string[];
  note?: string | null;
};
type QueryResponse = {
  category: string;
  situation_summary?: string;
  likely_outcome?: string;
  confidence?: string;
  win_probability?: number | null;
  win_label?: number | null;
  prediction_signals?: Signals;
  reasoning?: string;
  key_factors?: Factor[];
  what_would_strengthen?: string[];
  cited_cases?: CitedCase[];
  verification?: Verification;
  answer?: string;
  message?: string;
  out_of_scope?: boolean;
  web_sources?: { title: string; snippet: string; url: string }[];
  disclaimer?: string;
};

const EXAMPLES = [
  "My employer terminated me without notice or any inquiry after 12 years of service. Can I challenge the dismissal?",
  "The trial court rejected my suit for specific performance of an agreement to sell land. Should I appeal?",
  "A tax authority issued a reassessment notice four years after the original assessment. Is it valid?",
];

type ChatCited = {
  case_name: string;
  citation: string;
  court?: string;
  year?: number | null;
  outcome?: string;
  similarity: number;
  segment_role?: string;
  excerpt?: string;
};

type Item =
  | { id: number; role: "user"; text: string; fileName?: string }
  | { id: number; role: "assistant"; kind: "prediction"; data: QueryResponse }
  | { id: number; role: "assistant"; kind: "doc"; analysis: Analysis }
  | { id: number; role: "assistant"; kind: "text"; content: string; cases?: ChatCited[]; weak?: boolean }

  | { id: number; role: "assistant"; kind: "voice"; content: string; citations: string[] }
  | { id: number; role: "assistant"; kind: "error"; content: string };

const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.gif";
const MAX_BYTES = 10 * 1024 * 1024;

function isDocPayload(p: any): boolean {
  return !!p && typeof p.doc_id === "string" && (p.summary !== undefined || p.suggested_questions !== undefined);
}

function hydrate(messages: StoredMessage[], nextId: () => number): { items: Item[]; docId: string | null; predicted: boolean } {
  const items: Item[] = [];
  let docId: string | null = null;
  let predicted = false;
  for (const m of messages) {
    if (m.role === "user") {
      items.push({ id: nextId(), role: "user", text: m.content });
      continue;
    }
    const p = m.payload;
    if (p && typeof p.category === "string") {
      items.push({ id: nextId(), role: "assistant", kind: "prediction", data: p as QueryResponse });
      predicted = true;
    } else if (isDocPayload(p)) {
      items.push({ id: nextId(), role: "assistant", kind: "doc", analysis: p as Analysis });
      docId = p.doc_id;
    } else if (p?.source === "voice") {
      items.push({
        id: nextId(),
        role: "assistant",
        kind: "voice",
        content: m.content,
        citations: p.voice_citations || [],
      });
    } else {
      items.push({
        id: nextId(),
        role: "assistant",
        kind: "text",
        content: m.content,
        cases: p?.cited_cases,
        weak: p?.weak_retrieval,
      });
    }
  }
  return { items, docId, predicted };
}

export function AssessTab({ initialMessages }: { initialMessages?: StoredMessage[] }) {
  const { matter, sessionId, setSituation, attach, commitConv, resetConv } = useSession();

  const idRef = useRef(0);
  const nextId = () => ++idRef.current;

  const seed = useRef(
    initialMessages ? hydrate(initialMessages, nextId) : { items: [] as Item[], docId: null, predicted: false },
  ).current;

  const [items, setItems] = useState<Item[]>(seed.items);
  const [input, setInput] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [docId, setDocId] = useState<string | null>(seed.docId);
  const [predicted, setPredicted] = useState(seed.predicted);

  const seededMatter = useRef(seed.items.length > 0);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const botAudioRef = useRef<HTMLAudioElement>(null);
  const voice = useVoiceSession({ onComplete: (r) => absorbCall(r) });

  const push = (it: Item) => setItems((cur) => [...cur, it]);

  useEffect(() => {
    if (matter && input.trim() === "" && items.length === 0) setInput(matter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matter]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items, loading]);

  function pickFile(f: File | undefined) {
    if (!f) return;
    if (f.size > MAX_BYTES) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: "That file is over 10 MB. Please attach a smaller document.",
      });
      return;
    }
    setPendingFile(f);
  }

  async function analyzeFile(file: File): Promise<Analysis> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("session_id", sessionId);

    const r = await fetch("/api/doc/analyze", {
      method: "POST",
      headers: { ...(await authHeaders()) },
      body: fd,
    });
    const analysis = await readJsonResponse<Analysis>(r);
    commitConv("predict", (analysis as { conversation_id?: string }).conversation_id);
    return analysis;
  }

  const FULL_ASSESSMENT_RE =
    /\b(?:full|complete|detailed|proper|whole)\s+(?:case\s+)?(?:assessment|analysis|report|evaluation|breakdown)\b|\b(?:run|give|do|show)\s+(?:me\s+)?(?:the|a|an)?\s*(?:full\s+)?assessment\b|\bassess\s+(?:my|the|this)\s+(?:case|matter|situation)\b/i;

  function assessmentContext(): string {
    const parts: string[] = [];
    if (matter) parts.push(matter.trim());
    for (const it of items) {
      if (it.role === "user") {
        const t = it.text.trim();

        if (t && !FULL_ASSESSMENT_RE.test(t)) parts.push(t);
      } else if (it.kind === "voice") {
        parts.push(it.content.trim());
      }
    }

    return Array.from(new Set(parts.filter(Boolean))).join("\n\n");
  }

  function textHistory() {
    return items
      .filter((it) => it.role === "user" || (it.role === "assistant" && it.kind === "text"))
      .map((it) =>
        it.role === "user"
          ? { role: "user", content: it.text }
          : { role: "assistant", content: (it as Extract<Item, { kind: "text" }>).content },
      );
  }

  async function runFullAssessment() {
    if (loading) return;
    const question = assessmentContext();
    if (!question) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: "Tell me what happened first, then I can run the full assessment.",
      });
      return;
    }
    setLoading(true);
    try {
      const data = await postJson<QueryResponse & { conversation_id?: string }>(
        "/api/query",
        attach("predict", { question }),
      );
      commitConv("predict", data.conversation_id);
      push({ id: nextId(), role: "assistant", kind: "prediction", data });
      setPredicted(true);
    } catch (e) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: e instanceof Error ? e.message : "Request failed. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function send() {
    const text = input.trim();
    const file = pendingFile;
    if ((!text && !file) || loading) return;

    const firstUserTurn = !items.some((it) => it.role === "user");
    push({ id: nextId(), role: "user", text, fileName: file?.name });
    if (text && firstUserTurn && !seededMatter.current) {
      setSituation(text);
      seededMatter.current = true;
    }
    setInput("");
    setPendingFile(null);

    if (text && !file && !firstUserTurn && FULL_ASSESSMENT_RE.test(text)) {
      await runFullAssessment();
      return;
    }

    setLoading(true);
    try {
      if (file) {
        const analysis = await analyzeFile(file);
        setDocId(analysis.doc_id);
        push({ id: nextId(), role: "assistant", kind: "doc", analysis });
        if (text) {
          const d = await postJson<{ answer: string; conversation_id?: string }>(
            "/api/doc/chat",
            attach("predict", { doc_id: analysis.doc_id, question: text }),
          );
          commitConv("predict", d.conversation_id);
          push({ id: nextId(), role: "assistant", kind: "text", content: d.answer });
        }
      } else if (docId) {
        const d = await postJson<{ answer: string; conversation_id?: string }>(
          "/api/doc/chat",
          attach("predict", { doc_id: docId, question: text }),
        );
        commitConv("predict", d.conversation_id);
        push({ id: nextId(), role: "assistant", kind: "text", content: d.answer });
      } else if (!predicted) {
        const data = await postJson<QueryResponse & { conversation_id?: string }>(
          "/api/query",
          attach("predict", { question: text }),
        );
        commitConv("predict", data.conversation_id);
        push({ id: nextId(), role: "assistant", kind: "prediction", data });
        setPredicted(true);
      } else {
        const d = await postJson<{
          answer: string;
          cited_cases?: ChatCited[];
          weak_retrieval?: boolean;
          conversation_id?: string;
        }>("/api/chat", attach("predict", { question: text, history: textHistory() }));
        commitConv("predict", d.conversation_id);
        push({
          id: nextId(),
          role: "assistant",
          kind: "text",
          content: d.answer,
          cases: d.cited_cases,
          weak: d.weak_retrieval,
        });
      }
    } catch (e) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: e instanceof Error ? e.message : "Request failed. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function assessDoc(analysis: Analysis) {
    if (loading) return;
    const situation = (analysis.your_position || analysis.summary || analysis.title || "").trim();
    if (!situation) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: "Couldn't derive a situation from this document. Try one of the suggested questions instead.",
      });
      return;
    }
    push({ id: nextId(), role: "user", text: "Assess this document as a case" });
    if (!seededMatter.current) {
      setSituation(situation);
      seededMatter.current = true;
    }
    setLoading(true);
    try {
      const data = await postJson<QueryResponse & { conversation_id?: string }>(
        "/api/query",
        attach("predict", { question: situation }),
      );
      commitConv("predict", data.conversation_id);
      push({ id: nextId(), role: "assistant", kind: "prediction", data });
      setPredicted(true);
    } catch (e) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: e instanceof Error ? e.message : "Request failed.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function absorbCall({ summary, citations, firstQuestion }: CallResult) {
    const question = firstQuestion || "Voice consultation";
    push({ id: nextId(), role: "user", text: question });
    push({ id: nextId(), role: "assistant", kind: "voice", content: summary, citations });
    if (!seededMatter.current) {
      setSituation(question);
      seededMatter.current = true;
    }
    try {
      const d = await postJson<{ conversation_id?: string }>(
        "/api/voice/record",
        attach("predict", { question, summary, citations, tool: "predict" }),
      );
      commitConv("predict", d.conversation_id);
    } catch {}
  }

  async function askDoc(useDocId: string, question: string) {
    if (loading || !question.trim()) return;
    push({ id: nextId(), role: "user", text: question });
    setLoading(true);
    try {
      const d = await postJson<{ answer: string; conversation_id?: string }>(
        "/api/doc/chat",
        attach("predict", { doc_id: useDocId, question }),
      );
      commitConv("predict", d.conversation_id);
      push({ id: nextId(), role: "assistant", kind: "text", content: d.answer });
    } catch (e) {
      push({
        id: nextId(),
        role: "assistant",
        kind: "error",
        content: e instanceof Error ? e.message : "Request failed.",
      });
    } finally {
      setLoading(false);
    }
  }

  function startOver() {
    setItems([]);
    setDocId(null);
    setPredicted(false);
    setInput("");
    setPendingFile(null);
    seededMatter.current = false;
    resetConv("predict");
  }

  const voiceIdle = voice.phase === "idle";
  const empty = items.length === 0;

  const offerAssessmentOn = (() => {
    for (let i = items.length - 1; i >= 0; i -= 1) {
      const it = items[i];
      if (it.role !== "assistant") continue;
      if (it.kind === "prediction") return null;
      if (it.kind === "voice") return it.id;
    }
    return null;
  })();
  const latestDoc = [...items]
    .reverse()
    .find((it): it is Extract<Item, { kind: "doc" }> => it.role === "assistant" && it.kind === "doc");

  const composer = voiceIdle ? (
    <Composer
      input={input}
      setInput={setInput}
      pendingFile={pendingFile}
      onPick={pickFile}
      onClearFile={() => setPendingFile(null)}
      onSend={send}
      onVoice={() => voice.start(botAudioRef.current)}
      loading={loading}
      fileRef={fileRef}
    />
  ) : (
    <VoiceBar
      phase={voice.phase}
      status={voice.status}
      level={voice.level}
      agentSpeaking={voice.agentSpeaking}
      onStop={voice.stop}
      onCancel={voice.cancel}
    />
  );

  const zeroState = empty && voiceIdle;

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      {zeroState ? (
        <div className="flex flex-1 flex-col justify-center py-8">
          <Intro
            matter={matter ?? undefined}
            onExample={(ex) => setInput(ex)}
            onUseMatter={() => matter && setInput(matter)}
            composer={composer}
          />
        </div>
      ) : (
        <>
          <div className="flex justify-end">
            <button onClick={startOver} className="btn-ghost shrink-0 px-3 py-2 text-xs">
              Start over
            </button>
          </div>

          <div className="mt-2 flex-1 space-y-6 pb-4">
            {items.map((it) => (
              <Row
                key={it.id}
                item={it}

                onFullAssessment={
                  it.id === offerAssessmentOn && !loading ? runFullAssessment : undefined
                }
              />
            ))}
            {!loading && latestDoc && (
              <DocFollowUp analysis={latestDoc.analysis} onAssess={assessDoc} onAsk={askDoc} />
            )}
            {loading && <Thinking />}

            <LiveTurns turns={voice.turns} />
            <div ref={endRef} />
          </div>
          <div className="sticky bottom-4 pt-2">{composer}</div>
        </>
      )}

      <audio ref={botAudioRef} autoPlay />
    </div>
  );
}

function Row({ item, onFullAssessment }: { item: Item; onFullAssessment?: () => void }) {
  if (item.role === "user") return <UserBubble text={item.text} fileName={item.fileName} />;
  if (item.kind === "prediction")
    return (
      <FadeUp>
        <Result res={item.data} />
      </FadeUp>
    );
  if (item.kind === "doc")
    return (
      <FadeUp>
        <DocAnalysisView analysis={item.analysis} />
      </FadeUp>
    );
  if (item.kind === "voice")
    return (
      <FadeUp>
        <VoiceSummary
          content={item.content}
          citations={item.citations}
          onFullAssessment={onFullAssessment}
        />
      </FadeUp>
    );
  if (item.kind === "error")
    return (
      <div className="rounded-xl border border-red-300 bg-red-500/[0.06] px-4 py-3 text-sm text-red-600 dark:text-red-300">
        {item.content}
      </div>
    );
  return <AssistantText content={item.content} cases={item.cases} weak={item.weak} />;
}

function UserBubble({ text, fileName }: { text: string; fileName?: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] space-y-2">
        {fileName && (
          <div className="ml-auto flex w-fit items-center gap-2 rounded-xl border border-ink/15 bg-surface/70 px-3 py-2 text-xs text-ink/70">
            <DocIcon className="h-4 w-4 text-gold-600" />
            <span className="max-w-[200px] truncate">{fileName}</span>
          </div>
        )}
        {text && (
          <div className="whitespace-pre-wrap rounded-2xl bg-navy-900 px-4 py-2.5 text-sm leading-relaxed text-cream">
            {text}
          </div>
        )}
      </div>
    </div>
  );
}

function AssistantText({ content, cases, weak }: { content: string; cases?: ChatCited[]; weak?: boolean }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-3">
        <div className="whitespace-pre-wrap rounded-2xl border border-ink/10 bg-surface/70 px-4 py-3 text-sm leading-relaxed text-ink/85">
          {weak && (
            <div className="mb-2 inline-flex rounded-full bg-gold-400/15 px-2.5 py-0.5 text-[11px] font-medium text-gold-700">
              Limited matching cases
            </div>
          )}
          {content}
        </div>
        {cases && cases.length > 0 && (
          <div className="rounded-2xl border border-ink/10 bg-surface/50 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink/55">
                <ScalesIcon className="h-4 w-4 text-gold-600" /> Cases this answer is based on
              </div>
              <TrustBadge verified={cases.length} fabricated={0} />
            </div>
            <div className="mt-2.5 space-y-2">
              {cases.map((c, i) => (
                <CitedCaseCard key={i} c={c} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DocFollowUp({
  analysis,
  onAssess,
  onAsk,
}: {
  analysis: Analysis;
  onAssess: (a: Analysis) => void;
  onAsk: (docId: string, q: string) => void;
}) {
  const questions = analysis.suggested_questions.slice(0, 4);
  if (questions.length === 0 && !analysis.your_position && !analysis.summary) return null;

  return (
    <div className="card border border-gold-500/30 bg-gold-400/[0.05]">
      <div className="text-xs font-semibold uppercase tracking-wider text-gold-700">
        Keep going with this document
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onAssess(analysis)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-navy-900 px-3.5 py-1.5 text-xs font-semibold text-cream transition hover:bg-navy-800"
        >
          <ScalesIcon className="h-3.5 w-3.5 text-gold-400" /> Assess this as a case
        </button>
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onAsk(analysis.doc_id, q)}
            className="cursor-pointer rounded-full border border-ink/20 bg-surface px-3.5 py-1.5 text-left text-xs font-medium text-ink/80 transition hover:border-gold-500/40 hover:bg-gold-400/10 hover:text-ink"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function Intro({
  matter,
  onExample,
  onUseMatter,
  composer,
}: {
  matter?: string;
  onExample: (ex: string) => void;
  onUseMatter: () => void;
  composer: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="text-center font-serif text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
        What happened?
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-center text-sm leading-relaxed text-ink/60">
        Describe your situation and we&apos;ll tell you where you likely stand, grounded in how
        real Supreme Court cases were decided. Or attach a contract, notice, or order.
      </p>

      <div className="mt-6">{composer}</div>

      {matter && (
        <button
          onClick={onUseMatter}
          className="mt-4 block w-full rounded-xl border border-gold-500/30 bg-gold-400/10 px-4 py-3 text-left text-sm transition hover:border-gold-500/50"
        >
          <span className="block text-[11px] font-semibold uppercase tracking-wider text-gold-700">
            Continue your matter
          </span>
          <span className="mt-0.5 line-clamp-2 text-ink/70">{matter}</span>
        </button>
      )}

      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => onExample(ex)}
            className="rounded-full border border-ink/15 bg-surface/60 px-3.5 py-1.5 text-left text-xs text-ink/65 transition hover:border-ink/30 hover:text-ink"
          >
            {ex.length > 52 ? ex.slice(0, 52) + "…" : ex}
          </button>
        ))}
      </div>
    </div>
  );
}

function Composer({
  input,
  setInput,
  pendingFile,
  onPick,
  onClearFile,
  onSend,
  onVoice,
  loading,
  fileRef,
}: {
  input: string;
  setInput: (v: string) => void;
  pendingFile: File | null;
  onPick: (f: File | undefined) => void;
  onClearFile: () => void;
  onSend: () => void;
  onVoice: () => void;
  loading: boolean;
  fileRef: React.RefObject<HTMLInputElement>;
}) {
  const canSend = !loading && (input.trim().length > 0 || !!pendingFile);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  return (
    <div>
      <div className="group relative">
        <div
          aria-hidden
          className="pointer-events-none absolute -inset-px -z-10 rounded-[1.35rem] bg-[radial-gradient(120%_140%_at_50%_120%,rgba(var(--c-gold-500),0.22),transparent_70%)] opacity-0 blur-md transition-opacity duration-300 group-focus-within:opacity-100"
        />
        <div className="relative overflow-hidden rounded-[1.3rem] border border-ink/15 bg-surface/80 shadow-card backdrop-blur-md transition-colors duration-200 focus-within:border-gold-500/45">
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-px scale-x-0 bg-gradient-to-r from-transparent via-gold-500/60 to-transparent transition-transform duration-300 group-focus-within:scale-x-100"
          />

          {pendingFile && (
            <div className="mx-2.5 mt-2.5 flex items-center gap-2 rounded-xl border border-gold-500/25 bg-gold-500/[0.06] px-3 py-2 text-xs text-ink/80">
              <DocIcon className="h-4 w-4 shrink-0 text-gold-600" />
              <span className="min-w-0 flex-1 truncate">{pendingFile.name}</span>
              <button
                onClick={onClearFile}
                aria-label="Remove file"
                className="grid h-5 w-5 shrink-0 place-items-center rounded-md text-ink/40 transition hover:bg-ink/10 hover:text-ink"
              >
                ✕
              </button>
            </div>
          )}

          <div className="flex items-end gap-1.5 p-2.5">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              aria-label="Attach a document"
              title="Attach a document"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-ink/45 transition hover:bg-ink/[0.06] hover:text-gold-600"
            >
              <PaperclipIcon />
            </button>
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => {
                onPick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              rows={1}
              placeholder="Describe your situation, attach a document, or ask a question…"
              className="min-h-[36px] flex-1 resize-none self-center bg-transparent px-1 py-1.5 text-sm leading-relaxed text-ink outline-none placeholder:text-ink/40 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            />
            {voiceEnabled && (
              <button
                type="button"
                onClick={onVoice}
                aria-label="Start a voice conversation"
                title="Talk instead of typing"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-ink/45 transition hover:bg-ink/[0.06] hover:text-gold-600"
              >
                <Mic className="h-5 w-5" strokeWidth={1.8} aria-hidden />
              </button>
            )}
            <button
              onClick={onSend}
              disabled={!canSend}
              aria-label="Send"
              className="group/send grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand text-onbrand shadow-sm ring-1 ring-inset ring-white/10 transition-all duration-200 hover:shadow-lift enabled:hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowIcon className="h-4 w-4 transition-transform duration-200 group-enabled/send:group-hover/send:translate-x-0.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PaperclipIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.49" />
    </svg>
  );
}

function Thinking() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl border border-ink/10 bg-surface/70 px-4 py-3">
        <span className="flex gap-1">
          {[0, 0.15, 0.3].map((d) => (
            <span
              key={d}
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink/40"
              style={{ animationDelay: `${d}s` }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}

function Result({ res }: { res: QueryResponse }) {
  if (res.category === "not_legal") {
    if (res.out_of_scope && res.answer) return <OutOfScope res={res} />;
    return <Notice>{res.message}</Notice>;
  }
  if (res.category === "general_legal") {
    return (
      <section className="card">
        <h2 className="font-serif text-xl font-semibold text-ink">Answer</h2>
        <p className="mt-3 whitespace-pre-wrap leading-relaxed text-ink/80">{res.answer}</p>
      </section>
    );
  }

  const ps = res.prediction_signals;
  const winPct = typeof res.win_probability === "number" ? Math.round(res.win_probability * 100) : null;

  const copyText = [
    `Where you stand: ${stanceFor(winPct).headline}`,
    winPct !== null ? `Estimated chance of success: ~${winPct}% (based on analogous cases)` : "",
    `How confident: ${confidenceSentence(res.confidence)}`,
    res.situation_summary ? `\nYour situation: ${res.situation_summary}` : "",
    res.reasoning ? `\nWhat this means:\n${res.reasoning}` : "",
    res.cited_cases && res.cited_cases.length
      ? `\nCases this is based on:\n${res.cited_cases.map((c) => `- ${c.case_name} ${c.citation}`).join("\n")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink/45">Your assessment</span>
        <CopyButton text={copyText} label="Copy assessment" />
      </div>

      <FadeUp>
        <VerdictCard pct={winPct} confidence={res.confidence} precedent={ps?.precedent_vote} note={ps?.note} />
      </FadeUp>

      {res.reasoning && (
        <FadeUp delay={0.08} className="card">
          <h2 className="font-serif text-lg font-semibold text-ink">What this means for you</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink/80">{res.reasoning}</p>
        </FadeUp>
      )}

      {res.key_factors && res.key_factors.length > 0 && (
        <FadeUp delay={0.14}>
          <StrongWeakPoints factors={res.key_factors} />
        </FadeUp>
      )}

      {res.what_would_strengthen && res.what_would_strengthen.length > 0 && (
        <FadeUp delay={0.2}>
          <NextSteps steps={res.what_would_strengthen} />
        </FadeUp>
      )}

      {ps?.precedent_vote?.cases && ps.precedent_vote.cases.length > 0 && (
        <FadeUp delay={0.26}>
          <PrecedentList vote={ps.precedent_vote} />
        </FadeUp>
      )}

      {res.cited_cases && res.cited_cases.length > 0 && (
        <FadeUp delay={0.32} className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 font-serif text-lg font-semibold text-ink">
              <ScalesIcon className="h-5 w-5 text-gold-600" /> The cases this is based on
            </h2>
            {res.verification && (
              <TrustBadge verified={res.verification.verified_count} fabricated={res.verification.fabricated_count} />
            )}
          </div>
          <p className="mt-1 text-xs text-ink/55">
            Every case below is a real, indexed judgment, click any one to read it in full.
          </p>
          <div className="mt-3 space-y-2.5">
            {res.cited_cases.map((c, i) => (
              <CitedCaseCard key={i} c={c} />
            ))}
          </div>
        </FadeUp>
      )}

      {ps && (
        <FadeUp delay={0.36}>
          <MethodDisclosure ps={ps} />
        </FadeUp>
      )}
    </section>
  );
}

type Stance = { word: string; headline: string; tone: "good" | "neutral" | "bad" };

function stanceFor(pct: number | null): Stance {
  if (pct === null)
    return {
      word: "No clear lean",
      headline: "There isn't enough clear precedent to call this one either way.",
      tone: "neutral",
    };
  if (pct >= 65) return { word: "Strong position", headline: "Cases like yours usually succeed.", tone: "good" };
  if (pct >= 55) return { word: "Leans your way", headline: "The precedent leans in your favour.", tone: "good" };
  if (pct >= 45)
    return { word: "Finely balanced", headline: "This one is genuinely finely balanced.", tone: "neutral" };
  if (pct >= 35) return { word: "Leans against you", headline: "The precedent leans against you.", tone: "bad" };
  return { word: "Uphill case", headline: "This would be an uphill case.", tone: "bad" };
}

function confidenceSentence(confidence?: string): string {
  switch ((confidence ?? "").toLowerCase()) {
    case "high":
      return "We're fairly confident in this read of the precedent.";
    case "medium":
      return "We're reasonably confident, with some caveats.";
    case "low":
      return "Treat this cautiously, our signals don't fully agree, or there wasn't much closely-matching precedent.";
    default:
      return "Treat this as a starting point, not a firm answer.";
  }
}

const TONE: Record<Stance["tone"], { chip: string; bar: string; ring: string }> = {
  good: {
    chip: "bg-emerald-500/10 text-emerald-700 border-emerald-500/30",
    bar: "from-emerald-500 to-emerald-400",
    ring: "border-emerald-500/20",
  },
  neutral: {
    chip: "bg-gold-400/15 text-gold-700 border-gold-500/30",
    bar: "from-gold-500 to-gold-400",
    ring: "border-ink/10",
  },
  bad: {
    chip: "bg-red-500/10 text-red-600 border-red-500/30",
    bar: "from-red-500/80 to-red-400/80",
    ring: "border-red-500/20",
  },
};

function VerdictCard({
  pct,
  confidence,
  precedent,
  note,
}: {
  pct: number | null;
  confidence?: string;
  precedent?: Signals["precedent_vote"];
  note?: string | null;
}) {
  const s = stanceFor(pct);
  const tone = TONE[s.tone];

  const basis =
    precedent?.applicable && precedent.n_cases
      ? `Of ${precedent.n_cases} closely-matching Supreme Court ${
          precedent.n_cases === 1 ? "case" : "cases"
        }, ${precedent.won} ${precedent.won === 1 ? "was" : "were"} decided in the applicant's favour and ${precedent.lost} against.`
      : null;

  return (
    <div className={`card overflow-hidden border ${tone.ring}`}>
      <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">Where you stand</div>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <h2 className="max-w-xl font-serif text-2xl font-semibold leading-snug text-ink sm:text-3xl">{s.headline}</h2>
        <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${tone.chip}`}>{s.word}</span>
      </div>

      {basis && <p className="mt-3 text-sm leading-relaxed text-ink/70">{basis}</p>}

      {pct !== null && (
        <div className="mt-4">
          <div className="flex items-baseline justify-between">
            <span
              className="text-sm text-ink/60"
              title="An estimate of how often applicants in closely-matching past cases prevailed. It reflects the precedent, not a guarantee about your specific facts."
            >
              Estimated chance of success <span className="font-semibold text-ink">≈ {pct}%</span>
            </span>
          </div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-ink/10">
            <MotionBar pct={pct} delay={0.15} className={`h-full rounded-full bg-gradient-to-r ${tone.bar}`} />
          </div>
          <p className="mt-1.5 text-[11px] text-ink/45">
            A rough estimate from how similar past cases were decided, not a promise about yours.
          </p>
        </div>
      )}

      <div className="mt-4 rounded-lg bg-ink/[0.04] p-3 text-xs leading-relaxed text-ink/65">
        <span className="font-semibold text-ink/80">How sure are we? </span>
        {confidenceSentence(confidence)}
        {note && <span className="mt-1 block text-ink/55">{note}</span>}
      </div>
    </div>
  );
}

const ASSESSMENT_META: Record<Factor["assessment"], { tag: string; rail: string; chip: string; iconWrap: string }> = {
  favorable: {
    tag: "In your favour",
    rail: "border-l-emerald-500/70",
    chip: "bg-emerald-500/10 text-emerald-700 ring-emerald-500/25 dark:text-emerald-300",
    iconWrap: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  unfavorable: {
    tag: "Against you",
    rail: "border-l-red-500/70",
    chip: "bg-red-500/10 text-red-600 ring-red-500/25 dark:text-red-300",
    iconWrap: "bg-red-500/10 text-red-600 dark:text-red-400",
  },
  unclear: {
    tag: "Depends on detail",
    rail: "border-l-ink/25",
    chip: "bg-ink/5 text-ink/60 ring-ink/15",
    iconWrap: "bg-ink/5 text-ink/45",
  },
};

function FactorIcon({ kind }: { kind: Factor["assessment"] }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "h-4 w-4",
    "aria-hidden": true,
  };
  if (kind === "favorable")
    return (
      <svg {...common}>
        <path d="M3 17l6-6 4 4 8-8" />
        <path d="M17 7h4v4" />
      </svg>
    );
  if (kind === "unfavorable")
    return (
      <svg {...common}>
        <path d="M3 7l6 6 4-4 8 8" />
        <path d="M17 17h4v-4" />
      </svg>
    );
  return (
    <svg {...common}>
      <path d="M5 12h14" />
    </svg>
  );
}

function StrongWeakPoints({ factors }: { factors: Factor[] }) {
  const tally = {
    favorable: factors.filter((f) => f.assessment === "favorable").length,
    unfavorable: factors.filter((f) => f.assessment === "unfavorable").length,
    unclear: factors.filter((f) => f.assessment === "unclear").length,
  };

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-lg font-semibold text-ink">Your strong and weak points</h2>
          <p className="mt-1 text-xs text-ink/55">
            The factors the analogous cases turned on, weighed against your situation.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold">
          <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-emerald-700 dark:text-emerald-300">
            {tally.favorable} for
          </span>
          <span className="rounded-full bg-red-500/10 px-2 py-1 text-red-600 dark:text-red-300">
            {tally.unfavorable} against
          </span>
          <span className="rounded-full bg-ink/5 px-2 py-1 text-ink/55">{tally.unclear} depends</span>
        </div>
      </div>

      <ul className="mt-4 space-y-2">
        {factors.map((f, i) => {
          const m = ASSESSMENT_META[f.assessment] ?? ASSESSMENT_META.unclear;
          return (
            <li
              key={i}
              className={`flex items-start gap-3 rounded-lg border border-l-2 border-ink/10 bg-ink/[0.02] px-3.5 py-3 dark:bg-white/[0.02] ${m.rail}`}
            >
              <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md ${m.iconWrap}`}>
                <FactorIcon kind={f.assessment} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-sm font-semibold text-ink">{f.factor}</span>
                  <span
                    className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${m.chip}`}
                  >
                    {m.tag}
                  </span>
                </div>
                {f.reason && <p className="mt-1 text-xs leading-relaxed text-ink/65">{f.reason}</p>}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function NextSteps({ steps }: { steps: string[] }) {
  return (
    <div className="card border border-gold-500/30 bg-gold-400/[0.06]">
      <h2 className="font-serif text-lg font-semibold text-ink">What you can do next</h2>
      <p className="mt-1 text-xs text-ink/60">
        Concrete things that helped applicants in similar cases, worth discussing with an advocate.
      </p>
      <ul className="mt-4 space-y-2.5 text-sm text-ink/80">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-gold-500/20 text-[11px] font-semibold text-gold-700">
              {i + 1}
            </span>
            <span className="leading-relaxed">{step}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PrecedentList({ vote }: { vote: NonNullable<Signals["precedent_vote"]> }) {
  return (
    <div className="card">
      <h2 className="font-serif text-lg font-semibold text-ink">
        Real cases like yours{" "}
        <span className="text-sm font-normal text-ink/50">
          ({vote.won} won · {vote.lost} lost)
        </span>
      </h2>
      <p className="mt-1 text-xs text-ink/55">
        How the Supreme Court actually decided the closest matches to your situation.
      </p>
      <ul className="mt-3 space-y-2.5">
        {vote.cases!.map((c, i) => {
          const won = c.label === 1;
          return (
            <li
              key={i}
              className="flex items-center justify-between gap-3 rounded-lg border border-ink/10 bg-surface/60 px-4 py-3"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">{c.case_name}</div>
                <div className="text-xs text-ink/50">{c.citation || "Supreme Court of India"}</div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-xs tabular-nums text-ink/50">{Math.round(c.similarity * 100)}% similar</span>
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                    won ? "bg-emerald-500/10 text-emerald-700" : "bg-red-500/10 text-red-600"
                  }`}
                >
                  {won ? "Applicant won" : "Applicant lost"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MethodDisclosure({ ps }: { ps: Signals }) {
  const pv = ps.precedent_vote;
  const cls = ps.classifier;
  const llm = ps.llm_forecast;
  const fmt = (v: number | null | undefined) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "N/A");

  const llmDecided = !!llm?.likely_outcome && llm.likely_outcome !== "Uncertain";

  const rows = [
    {
      key: "Past cases",
      value: pv?.applicable ? fmt(pv.win_probability) : "N/A",
      sub: pv?.n_cases ? `${pv.won}/${pv.n_cases} similar cases were won` : "no decided matches",
    },
    {
      key: "Trained model",
      value: cls?.available ? fmt(cls.win_probability) : "N/A",
      sub: cls?.available ? "a model trained on past judgments" : "unavailable",
    },
    {
      key: "AI reasoning",
      value: llmDecided ? (llm!.label === 1 ? "in favour" : "against") : "No clear lean",
      sub: llmDecided ? "weighing the retrieved cases" : "didn't commit either way on these cases",
    },
  ];

  return (
    <details className="card group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span className="font-serif text-base font-semibold text-ink">How we worked this out</span>
        <span className="text-xs text-ink/50 transition group-open:hidden">Show the details</span>
        <span className="hidden text-xs text-ink/50 group-open:inline">Hide</span>
      </summary>
      <p className="mt-3 text-sm leading-relaxed text-ink/70">
        We don&apos;t rely on a single guess. Three independent signals weigh in, and our confidence depends on how
        much they agree, when they pull in different directions, we say so instead of pretending to be certain.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {rows.map((r) => (
          <div key={r.key} className="rounded-lg border border-ink/10 bg-surface/60 p-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-ink/50">{r.key}</div>
            <div className="mt-1.5 font-serif text-xl font-semibold text-ink">{r.value}</div>
            <div className="mt-1 text-[11px] leading-snug text-ink/55">{r.sub}</div>
          </div>
        ))}
      </div>
    </details>
  );
}

function OutOfScope({ res }: { res: QueryResponse }) {
  return (
    <section className="space-y-4">
      <div className="flex items-start gap-2 rounded-xl border border-gold-500/30 bg-gold-400/10 px-4 py-3 text-sm leading-relaxed text-ink/80">
        <span className="mt-0.5 shrink-0 rounded-full bg-gold-400/30 px-2 py-0.5 text-[11px] font-semibold text-gold-700">
          Outside legal scope
        </span>
        <span>{res.message}</span>
      </div>

      <div className="card">
        <p className="whitespace-pre-wrap leading-relaxed text-ink/85">{res.answer}</p>
      </div>

      {res.web_sources && res.web_sources.length > 0 && (
        <div className="card">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink/55">Sources from the web</h2>
          <ol className="mt-3 space-y-2">
            {res.web_sources.map((sourceItem, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="shrink-0 tabular-nums text-ink/40">[{i + 1}]</span>
                <a href={sourceItem.url} target="_blank" rel="noopener noreferrer" className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-gold-700 hover:underline">
                    {sourceItem.title || sourceItem.url}
                  </span>
                  <span className="block truncate text-xs text-ink/45">{sourceItem.url}</span>
                </a>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return <div className="card text-ink/75">{children}</div>;
}
