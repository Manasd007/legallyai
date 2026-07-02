"use client";

import { useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  useScroll,
  useMotionValueEvent,
} from "framer-motion";
import { ScalesIcon, ChatIcon, BookIcon, DocIcon } from "@/components/ui";
import { EASE, GoldLine, Reveal } from "@/components/motion";

type Frame = {
  id: string;
  nav: string;
  icon: typeof ScalesIcon;
  title: string;
  body: string;
  render: () => JSX.Element;
};

/* ------------------------------ Faux screens ------------------------------ */

function AssessScreen() {
  return (
    <div className="space-y-5">
      <div className="border-l-2 border-gold-500/40 pl-4">
        <p className="text-[11px] font-medium uppercase tracking-wider text-ink/45">Your situation</p>
        <p className="mt-1.5 text-sm leading-relaxed text-ink/75">
          “My employer terminated me without notice or inquiry after 12 years of service.”
        </p>
      </div>
      <div>
        <div className="flex items-end justify-between gap-4">
          <span className="text-[11px] font-medium uppercase tracking-wider text-ink/45">
            Success estimate
          </span>
          <span className="font-serif text-3xl font-semibold tabular-nums leading-none text-ink">
            75<span className="ml-0.5 text-lg text-ink/40">%</span>
          </span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-ink/10">
          <motion.div
            className="h-full rounded-full bg-gold-500"
            initial={{ width: 0 }}
            animate={{ width: "75%" }}
            transition={{ duration: 0.9, ease: EASE }}
          />
        </div>
      </div>
      <div className="space-y-2.5 border-t border-ink/10 pt-4">
        <div className="flex gap-2.5 text-sm">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold-500" />
          <span className="text-ink/65"><span className="font-medium text-ink/85">Helps you:</span> 12 years of service</span>
        </div>
        <div className="flex gap-2.5 text-sm">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink/25" />
          <span className="text-ink/60"><span className="font-medium text-ink/75">Depends on:</span> how you were dismissed</span>
        </div>
      </div>
      <div className="rounded-xl border border-ink/10 bg-surface/60 px-4 py-3 text-xs leading-relaxed text-ink/55">
        Based on <span className="font-medium text-ink/80">4 similar Supreme Court cases</span>, 3 of 4 decided in the claimant&apos;s favour.
      </div>
    </div>
  );
}

function AskScreen() {
  return (
    <div className="space-y-4">
      <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-navy-900 px-4 py-2.5 text-sm text-cream">
        Is a dismissal without inquiry valid for a workman?
      </div>
      <div className="max-w-[88%] space-y-3">
        <p className="text-sm leading-relaxed text-ink/80">
          Generally no. For a workman, dismissal without a fair domestic inquiry is procedurally
          defective, and courts look closely at whether natural justice was followed.
        </p>
        <div className="space-y-2">
          {[
            ["Workmen of M/s Firestone v. Mgmt.", "1973 INSC 4"],
            ["Delhi Transport Corp. v. DTC Mazdoor", "1990 INSC 285"],
          ].map(([name, cite]) => (
            <div key={cite} className="flex items-center gap-2.5 rounded-lg border border-ink/10 bg-surface/60 px-3 py-2">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-navy-900 text-gold-400">
                <BookIcon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-xs font-semibold text-ink">{name}</span>
                <span className="block text-[11px] text-ink/50">{cite} · verified</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FindScreen() {
  return (
    <div className="space-y-3">
      <div className="text-[11px] font-medium uppercase tracking-wider text-ink/45">Acts &amp; sections that govern this</div>
      {[
        ["Industrial Disputes Act, 1947", "S. 25F: Conditions precedent to retrenchment", "6 cases interpret this"],
        ["Industrial Disputes Act, 1947", "S. 11A: Powers of the Tribunal on dismissal", "4 cases interpret this"],
        ["Constitution of India", "Art. 14: Equality & fairness in State action", "9 cases interpret this"],
      ].map(([act, sec, cases], i) => (
        <div key={i} className="rounded-xl border border-ink/10 bg-surface/60 p-3.5">
          <div className="text-xs font-semibold text-ink">{act}</div>
          <div className="mt-1 text-sm text-ink/70">{sec}</div>
          <div className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-gold-700">
            <span className="h-1 w-1 rounded-full bg-gold-500" /> {cases}
          </div>
        </div>
      ))}
    </div>
  );
}

function DocScreen() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 rounded-xl border border-ink/10 bg-surface/60 px-3.5 py-2.5">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-navy-900 text-gold-400">
          <DocIcon className="h-4 w-4" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-ink">Termination_Letter.pdf</span>
          <span className="block text-[11px] text-ink/50">4 pages · analysed in seconds</span>
        </span>
      </div>
      <div>
        <div className="text-[11px] font-medium uppercase tracking-wider text-ink/45">List of dates</div>
        <div className="mt-2 space-y-2">
          {[
            ["12 Jan 2012", "Joined as permanent workman"],
            ["03 Mar 2024", "Terminated: no notice, no inquiry"],
          ].map(([d, e]) => (
            <div key={d} className="flex gap-3 text-sm">
              <span className="w-24 shrink-0 font-mono text-[11px] text-ink/55">{d}</span>
              <span className="text-ink/75">{e}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 border-t border-ink/10 pt-3">
        {["Wrongful termination", "No inquiry", "Workman", "12 yrs service"].map((t) => (
          <span key={t} className="rounded-full border border-ink/10 bg-surface/60 px-2.5 py-1 text-[11px] text-ink/60">
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

const FRAMES: Frame[] = [
  {
    id: "assess",
    nav: "Assess a case",
    icon: ScalesIcon,
    title: "See where your case stands.",
    body: "Describe your situation and get an honest success estimate, weighed against how real Supreme Court cases were decided.",
    render: AssessScreen,
  },
  {
    id: "ask",
    nav: "Ask a question",
    icon: ChatIcon,
    title: "Ask the law, get cited answers.",
    body: "Every reply links to the actual judgments behind it. No fabricated cases, so you can always check the source.",
    render: AskScreen,
  },
  {
    id: "find",
    nav: "Find the law",
    icon: BookIcon,
    title: "Pinpoint the governing law.",
    body: "Jump straight to the Acts and sections that apply, each linked to the cases that interpret them.",
    render: FindScreen,
  },
  {
    id: "docs",
    nav: "Read a document",
    icon: DocIcon,
    title: "Drop a document, get the gist.",
    body: "Attach a letter, notice, or order right inside Assess a case — Legally AI pulls out the dates, parties, and issues that matter.",
    render: DocScreen,
  },
];

/* ------------------------------ Demo section ------------------------------ */

export function DashboardDemo() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  });

  useMotionValueEvent(scrollYProgress, "change", (p) => {
    const idx = Math.min(FRAMES.length - 1, Math.max(0, Math.floor(p * FRAMES.length)));
    setActive(idx);
  });

  const Screen = FRAMES[active].render;

  return (
    <div id="demo">
      {/* Mobile & tablet: no scroll-jacking (a pinned scrub feels endless and
          cramped below lg) — instead each tool gets its own full-width card,
          with the real app-window mockup, that fades in as it's scrolled to. */}
      <section className="bg-navy-950 py-16 text-cream lg:hidden">
        <div className="container-page">
          <span className="eyebrow text-gold-400">
            <GoldLine className="h-px w-6 bg-gold-400" />A quick tour
          </span>
          <h2 className="mt-4 font-serif text-3xl font-semibold tracking-tight">
            One workspace, the whole matter.
          </h2>
          <p className="mt-4 max-w-md text-cream/65">
            Describe your situation once. It follows you across every tool.
          </p>
        </div>

        <div className="container-page mt-10 space-y-14">
          {FRAMES.map((f) => {
            const Icon = f.icon;
            const FrameScreen = f.render;
            return (
              <Reveal key={f.id} className="space-y-4">
                <div className="flex items-center gap-3">
                  <Icon className="h-6 w-6 shrink-0 text-gold-500" />
                  <div className="text-sm font-semibold text-cream">{f.nav}</div>
                </div>
                <p className="text-sm leading-relaxed text-cream/65">{f.body}</p>

                <div className="relative">
                  <div
                    aria-hidden
                    className="absolute -inset-4 -z-10 rounded-3xl bg-[radial-gradient(ellipse_at_50%_0%,rgba(var(--c-gold-500),0.16),transparent_65%)]"
                  />
                  <div className="overflow-hidden rounded-2xl border border-white/10 bg-parchment text-ink shadow-lift">
                    <div className="flex items-center gap-2 border-b border-ink/10 bg-surface/70 px-4 py-2.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                      <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                      <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                      <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.18em] text-ink/35">
                        legally.ai / workspace
                      </span>
                    </div>
                    <div className="p-5">
                      <h3 className="font-serif text-lg font-semibold text-ink">{f.title}</h3>
                      <div className="mt-4">
                        <FrameScreen />
                      </div>
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* Desktop: scroll-pinned walkthrough, narrative column + live mockup */}
      <section
        ref={ref}
        className="relative hidden bg-navy-950 text-cream lg:block"
        style={{ height: reduce ? "auto" : `${FRAMES.length * 100}vh` }}
      >
        <div className={reduce ? "py-20" : "sticky top-0 flex min-h-screen items-center py-20"}>
        <div className="container-page grid w-full items-center gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
          {/* Narrative column */}
          <div>
            <span className="eyebrow text-gold-400">
              <GoldLine className="h-px w-6 bg-gold-400" />A quick tour
            </span>
            <h2 className="mt-4 font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
              One workspace, the whole matter.
            </h2>
            <p className="mt-4 max-w-md text-cream/65">
              Describe your situation once. It follows you across every tool. Scroll to walk through
              the dashboard.
            </p>

            <div className="mt-9 space-y-1.5">
              {FRAMES.map((f, i) => {
                const Icon = f.icon;
                const on = i === active;
                return (
                  <div
                    key={f.id}
                    className={`flex gap-3.5 rounded-xl border px-4 py-3.5 transition-colors duration-300 ${
                      on ? "border-gold-500/40 bg-white/[0.06]" : "border-transparent"
                    }`}
                  >
                    <span
                      className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg transition-colors duration-300 ${
                        on ? "bg-gold-500 text-navy-950" : "bg-white/10 text-cream/60"
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <div className={`text-sm font-semibold ${on ? "text-cream" : "text-cream/70"}`}>
                        {f.nav}
                      </div>
                      <AnimatePresence initial={false} mode="wait">
                        {on && (
                          <motion.p
                            key={f.id}
                            initial={reduce ? false : { opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={reduce ? undefined : { opacity: 0, height: 0 }}
                            transition={{ duration: 0.35, ease: EASE }}
                            className="overflow-hidden text-sm leading-relaxed text-cream/60"
                          >
                            <span className="block pt-1">{f.body}</span>
                          </motion.p>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* App-window mockup */}
          <div className="relative">
            <div
              aria-hidden
              className="absolute -inset-6 -z-10 rounded-3xl bg-[radial-gradient(ellipse_at_50%_0%,rgba(var(--c-gold-500),0.18),transparent_65%)]"
            />
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-parchment text-ink shadow-lift">
              {/* Window chrome */}
              <div className="flex items-center gap-2 border-b border-ink/10 bg-surface/70 px-4 py-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
                <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.18em] text-ink/35">
                  legally.ai / workspace
                </span>
              </div>

              <div className="grid sm:grid-cols-[150px_1fr]">
                {/* Faux sidebar — only the 3 real workspace tabs; the doc
                    frame lives inside "Assess a case", so it highlights that. */}
                <div className="hidden flex-col gap-1 border-r border-ink/10 bg-surface/40 p-3 sm:flex">
                  {FRAMES.slice(0, 3).map((f, i) => {
                    const Icon = f.icon;
                    const on = i === (active === 3 ? 0 : active);
                    return (
                      <div
                        key={f.id}
                        className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-[11px] font-medium transition-colors duration-300 ${
                          on ? "bg-navy-900 text-cream" : "text-ink/55"
                        }`}
                      >
                        <Icon className={`h-4 w-4 shrink-0 ${on ? "text-gold-400" : "text-ink/45"}`} />
                        <span className="truncate">{f.nav}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Active screen */}
                <div className="min-h-[340px] p-5 sm:p-6">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={FRAMES[active].id}
                      initial={reduce ? false : { opacity: 0, y: 14 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduce ? undefined : { opacity: 0, y: -14 }}
                      transition={{ duration: 0.4, ease: EASE }}
                    >
                      <h3 className="font-serif text-lg font-semibold text-ink">{FRAMES[active].title}</h3>
                      <div className="mt-4">
                        <Screen />
                      </div>
                    </motion.div>
                  </AnimatePresence>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </section>
    </div>
  );
}
