"use client";

import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { ArrowIcon, ScalesIcon, ChatIcon } from "@/components/ui";
import { useSession } from "@/components/session";
import { CitedCase as CitedCaseCard, TrustBadge } from "@/components/CitedCase";
import { postJson } from "@/components/api";
import { useVoiceSession, useVoiceEnabled, type CallResult } from "@/components/voice/useVoiceSession";
import { VoiceBar } from "@/components/voice/VoiceBar";
import { LiveTurns } from "@/components/voice/LiveTurns";
import { VoiceSummary } from "@/components/VoiceSummary";
import { TabIntro } from "@/components/tabs/TabIntro";
import type { StoredMessage } from "@/components/tabs/types";

type Cited = {
  case_name: string;
  citation: string;
  court: string;
  year: number | null;
  outcome: string;
  similarity: number;
  segment_role?: string;
  excerpt?: string;
};
type Msg = {
  role: "user" | "assistant";
  content: string;
  cases?: Cited[];
  weak?: boolean;
  caution?: boolean;

  voiceCitations?: string[];
};

const STARTERS = [
  "Can an employer dismiss an employee without an inquiry?",
  "When can a suit for specific performance of a sale agreement succeed?",
  "What are the grounds to challenge a tax reassessment notice?",
  "Is anticipatory bail available for economic offences?",
];

function hydrate(messages: StoredMessage[]): Msg[] {
  return messages.map((m) =>
    m.role === "user"
      ? { role: "user", content: m.content }
      : {
          role: "assistant",
          content: m.content,
          cases: m.payload?.cited_cases,
          weak: m.payload?.weak_retrieval,
          caution: m.payload?.grounding_caution,
          voiceCitations: m.payload?.voice_citations,
        },
  );
}

export function AskTab({ initialMessages }: { initialMessages?: StoredMessage[] }) {
  const { matter, setSituation, attach, commitConv } = useSession();
  const [messages, setMessages] = useState<Msg[]>(() =>
    initialMessages ? hydrate(initialMessages) : [],
  );
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const botAudioRef = useRef<HTMLAudioElement>(null);
  const voiceEnabled = useVoiceEnabled();
  const voice = useVoiceSession({ onComplete: (r) => absorbCall(r) });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function ask(question: string) {
    if (!question.trim() || loading) return;

    if (messages.length === 0) setSituation(question);
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    try {
      const data = await postJson<{
        answer: string;
        cited_cases?: Cited[];
        weak_retrieval?: boolean;
        grounding_caution?: boolean;
        conversation_id?: string;
      }>("/api/chat", attach("assistant", { question, history }));
      commitConv("assistant", data.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer,
          cases: data.cited_cases,
          weak: data.weak_retrieval,
          caution: data.grounding_caution,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: e instanceof Error ? e.message : "Request failed." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function absorbCall({ summary, citations, firstQuestion }: CallResult) {
    const question = firstQuestion || "Voice consultation";
    if (messages.length === 0) setSituation(question);
    setMessages((m) => [
      ...m,
      { role: "user", content: question },
      { role: "assistant", content: summary, voiceCitations: citations },
    ]);
    try {
      const data = await postJson<{ conversation_id?: string }>(
        "/api/voice/record",
        attach("assistant", { question, summary, citations, tool: "assistant" }),
      );
      commitConv("assistant", data.conversation_id);
    } catch {}
  }

  const voiceIdle = voice.phase === "idle";

  const composer = voiceIdle ? (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        ask(input);
      }}
      className="flex items-center gap-2 rounded border-2 border-ink bg-surface/70 px-2 py-1.5 shadow-brutal-sm backdrop-blur-md"
    >
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask a legal question…"
        className="flex-1 bg-transparent px-2 py-2 text-sm text-ink outline-none placeholder:text-ink/40"
      />
      {voiceEnabled && (
        <button
          type="button"
          onClick={() => voice.start(botAudioRef.current)}
          title="Talk instead of typing"
          aria-label="Start a voice conversation"
          className="rounded border-2 border-transparent p-2 text-ink/50 transition hover:border-ink hover:bg-ink/5 hover:text-ink"
        >
          <Mic className="h-4 w-4" strokeWidth={1.8} aria-hidden />
        </button>
      )}
      <button type="submit" disabled={loading || !input.trim()} className="btn-primary px-3 py-2">
        <ArrowIcon className="h-4 w-4" />
      </button>
    </form>
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

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col">
      {messages.length === 0 && voiceIdle ? (
        <TabIntro
          icon={ChatIcon}
          title="What would you like to know?"
          subtitle="Every answer shows the Supreme Court cases it relied on, and follow-ups remember what you asked before."
          composer={composer}
          matter={matter}
          onUseMatter={() => matter && ask(matter)}
          examples={STARTERS.map((q) => ({
            label: q.length > 52 ? q.slice(0, 52) + "…" : q,
            onClick: () => ask(q),
          }))}
        />
      ) : (
        <>

          <div className="flex-1 space-y-4 pb-4">
            {messages.map((m, i) => (
              <MessageBubble key={i} msg={m} />
            ))}
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

function MessageBubble({ msg }: { msg: Msg }) {
  if (msg.role === "assistant" && msg.voiceCitations) {
    return <VoiceSummary content={msg.content} citations={msg.voiceCitations} />;
  }
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded border-2 border-ink bg-navy-900 px-4 py-2.5 text-sm leading-relaxed text-cream shadow-brutal-sm">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-3">
        <div className="whitespace-pre-wrap rounded border-2 border-ink bg-surface/65 px-4 py-3 text-sm leading-relaxed text-ink/85 backdrop-blur-md">
          {(msg.weak || msg.caution) && (
            <div className="mb-2 inline-flex rounded border-2 border-gold-500/50 bg-gold-400/15 px-2.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-gold-700">
              {msg.weak ? "Limited matching cases" : "Verify against the cited cases"}
            </div>
          )}
          {msg.content}
        </div>
        {msg.cases && msg.cases.length > 0 && (
          <div className="rounded border-2 border-ink bg-surface/45 px-4 py-3 backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/55">
                <ScalesIcon className="h-4 w-4 text-gold-600" /> Cases this answer is based on
              </div>
              <TrustBadge verified={msg.cases.length} fabricated={0} />
            </div>
            <div className="mt-2.5 space-y-2">
              {msg.cases.map((c, i) => (
                <CitedCaseCard key={i} c={c} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex justify-start">
      <div className="rounded border-2 border-ink bg-surface/65 px-4 py-3 backdrop-blur-md">
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
