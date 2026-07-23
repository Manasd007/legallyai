"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { EASE } from "@/components/motion";
import { turnText, type Turn } from "@/components/voice/useVoiceSession";

export function LiveTurns({ turns }: { turns: Turn[] }) {
  const reduce = useReducedMotion();

  const visible = turns.filter((t) => turnText(t).length > 0);

  return (
    <AnimatePresence initial={false}>
      {visible.map((t) => {
        const you = t.role === "user";
        return (
          <motion.div
            key={`${t.role}-${t.turn}`}
            layout={!reduce}
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.32, ease: EASE }}
            className={`flex ${you ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                you
                  ? "bg-navy-900 text-cream"
                  : "border border-ink/10 bg-surface/70 text-ink/85"
              }`}
            >
              {t.final}

              {t.partial && (
                <>
                  {t.final ? " " : ""}
                  <span className={you ? "text-cream/60" : "text-ink/45"}>{t.partial}</span>
                </>
              )}
              {!reduce && t.partial && (
                <motion.span
                  aria-hidden
                  className={`ml-0.5 inline-block h-[1em] w-px align-text-bottom ${
                    you ? "bg-cream/70" : "bg-ink/50"
                  }`}
                  animate={{ opacity: [1, 0.15, 1] }}
                  transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
                />
              )}
            </div>
          </motion.div>
        );
      })}
    </AnimatePresence>
  );
}
