"use client";

import {
  AnimatePresence,
  animate,
  motion,
  useInView,
  useReducedMotion,
  type Variants,
} from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";

export const EASE = [0.22, 1, 0.36, 1] as const;


export function Reveal({
  children,
  className,
  delay = 0,
  y = 16,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
  as?: "div" | "span" | "section" | "li" | "h1" | "h2" | "p";
}) {
  const reduce = useReducedMotion();
  const M = (motion as any)[as];
  return (
    <M
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      {children}
    </M>
  );
}


export function Stagger({
  children,
  className,
  gap = 0.06,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  gap?: number;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-90px" }}
      variants={{ show: { transition: { staggerChildren: gap, delayChildren: delay } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
  y = 14,
}: {
  children: ReactNode;
  className?: string;
  y?: number;
}) {
  const reduce = useReducedMotion();
  const variants: Variants = reduce
    ? { hidden: {}, show: {} }
    : {
        hidden: { opacity: 0, y },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
      };
  return (
    <motion.div className={className} variants={variants}>
      {children}
    </motion.div>
  );
}


export function GoldLine({ className = "h-0.5 w-6 bg-gold-500" }: { className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.span
      className={`block origin-left ${className}`}
      initial={reduce ? false : { scaleX: 0 }}
      whileInView={reduce ? undefined : { scaleX: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.7, ease: EASE }}
    />
  );
}


export function MotionBar({
  pct,
  className,
  delay = 0.1,
}: {
  pct: number;
  className?: string;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { width: 0 }}
      whileInView={{ width: `${pct}%` }}
      viewport={{ once: true }}
      transition={{ duration: 0.9, ease: EASE, delay }}
    />
  );
}


export function CountUp({
  to,
  suffix = "",
  className,
  duration = 1.3,
}: {
  to: number;
  suffix?: string;
  className?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reduce = useReducedMotion();
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setVal(to);
      return;
    }
    const controls = animate(0, to, {
      duration,
      ease: EASE,
      onUpdate: (v) => setVal(v),
    });
    return () => controls.stop();
  }, [inView, to, reduce, duration]);

  return (
    <span ref={ref} className={className}>
      {Math.round(val).toLocaleString()}
      {suffix}
    </span>
  );
}


export function Rotator({
  items,
  interval = 2200,
  className,
}: {
  items: string[];
  interval?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduce || items.length <= 1) return;
    const id = setInterval(() => setI((v) => (v + 1) % items.length), interval);
    return () => clearInterval(id);
  }, [items.length, interval, reduce]);

  return (
    <span className={`relative inline-grid overflow-hidden align-bottom ${className ?? ""}`}>
      <span aria-hidden className="invisible col-start-1 row-start-1 whitespace-nowrap">
        {items.reduce((a, b) => (a.length >= b.length ? a : b), "")}
      </span>
      <AnimatePresence mode="sync" initial={false}>
        <motion.span
          key={items[i]}
          className="col-start-1 row-start-1 whitespace-nowrap"
          initial={reduce ? false : { y: "0.8em", opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={reduce ? undefined : { y: "-0.8em", opacity: 0 }}
          transition={{ duration: 0.45, ease: EASE }}
        >
          {items[i]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}


export function Marquee({
  items,
  className,
}: {
  items: string[];
  className?: string;
}) {
  const doubled = [...items, ...items];
  return (
    <div className={`marquee-mask w-full overflow-hidden ${className ?? ""}`}>
      <div className="flex w-max animate-marquee gap-3 pr-3">
        {doubled.map((t, idx) => (
          <span
            key={`${t}-${idx}`}
            className="inline-flex items-center whitespace-nowrap rounded border-2 border-ink/20 bg-surface/50 px-4 py-1.5 font-mono text-xs uppercase tracking-[0.08em] text-ink/60 backdrop-blur-sm"
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}


const REVEAL_EASE = [0, 0.75, 0.25, 0.98] as const;

export function MaskedTextReveal({
  text,
  as = "h1",
  className,
  highlight = [],
  stagger = 0.08,
  fromY = 140,
  rotateFrom = 4,
  blur = 0,
  delay = 0.2,
  duration = 1,
  once = true,
  amount = 0.4,
  maskPad = 6,
}: {
  text: string;
  as?: "h1" | "h2" | "h3" | "p" | "div";
  className?: string;
  highlight?: string[];
  stagger?: number;
  fromY?: number;
  rotateFrom?: number;
  blur?: number;
  delay?: number;
  duration?: number;
  once?: boolean;
  amount?: number;
  maskPad?: number;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once, amount });
  const words = text.trim().split(/\s+/g);
  const highlightSet = new Set(highlight.map((w) => w.replace(/[^\p{L}\p{N}]/gu, "").toLowerCase()));

  const variants: Variants = {
    hidden: {
      y: fromY,
      rotate: rotateFrom,
      filter: blur > 0 ? `blur(${blur}px)` : "blur(0px)",
    },
    visible: (i: number) => ({
      y: 0,
      rotate: 0,
      filter: "blur(0px)",
      transition: { type: "tween", ease: REVEAL_EASE, duration, delay: delay + i * stagger },
    }),
  };

  const M = (motion as any)[as];
  const show = reduce || inView;

  return (
    <M
      ref={ref}
      aria-label={text}
      className={className}
      style={{ display: "flex", flexWrap: "wrap", columnGap: "0.28em", overflow: "visible" }}
    >
      {words.map((w, i) => {
        const isGold = highlightSet.has(w.replace(/[^\p{L}\p{N}]/gu, "").toLowerCase());
        const pad = `max(${maskPad}px, 0.14em)`;
        return (
          <span
            key={`${w}-${i}`}
            aria-hidden
            style={{
              display: "inline-flex",
              overflow: "hidden",
              paddingBottom: pad,
              marginBottom: `calc(-1 * (${pad}))`,
            }}
          >
            <motion.span
              custom={i}
              variants={reduce ? undefined : variants}
              initial={reduce ? false : "hidden"}
              animate={reduce ? false : show ? "visible" : "hidden"}
              className={isGold ? "text-gold-600" : undefined}
              style={{ display: "inline-block", transformOrigin: "50% 100%", willChange: "transform, filter" }}
            >
              {w}
            </motion.span>
          </span>
        );
      })}
    </M>
  );
}


export function FadeUp({
  children,
  className,
  delay = 0,
  y = 14,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      animate={reduce ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}
