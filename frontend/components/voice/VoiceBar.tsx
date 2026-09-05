"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Mic, Check, X } from "lucide-react";
import { EASE } from "@/components/motion";
import type { Phase } from "@/components/voice/useVoiceSession";

const BAR_COUNT = 28;

function LevelMeter({ level, active }: { level: number; active: boolean }) {
  const reduce = useReducedMotion();

  return (
    <div className="flex h-8 flex-1 items-center justify-center gap-[3px]" aria-hidden>
      {Array.from({ length: BAR_COUNT }).map((_, i) => {
        const d = Math.abs(i - (BAR_COUNT - 1) / 2) / ((BAR_COUNT - 1) / 2);
        const bell = Math.cos((d * Math.PI) / 2) ** 1.5;
        const h = active ? 3 + level * 26 * bell * (0.75 + 0.5 * Math.random()) : 3;
        return (
          <motion.span
            key={i}
            className="w-[3px] rounded-full bg-gold-500/70"
            animate={reduce ? { height: 3 } : { height: Math.max(3, h) }}
            transition={{ duration: 0.12, ease: "easeOut" }}
          />
        );
      })}
    </div>
  );
}

export function VoiceBar({
  phase,
  status,
  level,
  agentSpeaking,
  onStop,
  onCancel,
}: {
  phase: Phase;
  status: string;
  level: number;
  agentSpeaking: boolean;
  onStop: () => void;
  onCancel: () => void;
}) {
  const reduce = useReducedMotion();
  const live = phase === "live";
  const summarizing = phase === "summarizing";

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE }}
      className="relative overflow-hidden rounded border-2 border-ink bg-surface/70 shadow-brutal-sm backdrop-blur-md"
    >

      {!reduce && !live && (
        <motion.div
          aria-hidden
          className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-gold-500/10 to-transparent"
          animate={{ x: ["-100%", "400%"] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />
      )}

      <div className="relative flex items-center gap-3 p-2.5">
        <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded border-2 border-gold-500/50 bg-gold-500/15 text-gold-600">
          {live && !reduce && (
            <motion.span
              className="absolute inset-0 rounded bg-gold-500/25"
              animate={{ scale: [1, 1.35], opacity: [0.5, 0] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
            />
          )}
          <Mic className="relative h-4 w-4" strokeWidth={1.8} aria-hidden />
        </span>

        <LevelMeter level={agentSpeaking ? 0.12 : level} active={live} />

        <span
          className="min-w-[7.5rem] shrink-0 text-right text-xs font-medium text-ink/55"
          aria-live="polite"
        >
          {agentSpeaking && live ? "Speaking…" : status}
        </span>

        {live ? (
          <button
            type="button"
            onClick={onStop}
            title="Finish and write up"
            aria-label="Finish the voice conversation"
            className="grid h-9 w-9 shrink-0 place-items-center rounded border-2 border-ink bg-brand text-onbrand shadow-brutal-sm transition hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-brutal active:translate-x-0 active:translate-y-0 active:shadow-none"
          >
            <Check className="h-4 w-4" strokeWidth={2} aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            onClick={onCancel}
            disabled={summarizing}
            title="Cancel"
            aria-label="Cancel the voice conversation"
            className="grid h-9 w-9 shrink-0 place-items-center rounded border-2 border-transparent text-ink/45 transition hover:border-ink hover:bg-ink/[0.06] hover:text-ink disabled:opacity-40"
          >
            <X className="h-4 w-4" strokeWidth={2} aria-hidden />
          </button>
        )}
      </div>
    </motion.div>
  );
}
