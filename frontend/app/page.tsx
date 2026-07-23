import Link from "next/link";
import {
  Nav,
  Footer,
  ArrowIcon,
  ScalesIcon,
  ChatIcon,
  BookIcon,
} from "@/components/ui";
import { Reveal, Stagger, StaggerItem, GoldLine, MotionBar, Marquee, MaskedTextReveal } from "@/components/motion";
import { DashboardDemo } from "@/components/DashboardDemo";

const PRACTICE_AREAS = [
  "Wrongful termination",
  "Security deposit disputes",
  "Cheque bounce · S.138",
  "Consumer complaints",
  "Property & tenancy",
  "Maintenance & alimony",
  "Service matters",
  "Defamation",
  "Motor accident claims",
  "Bail & quashing",
];

const CAPABILITIES: {
  icon: typeof ScalesIcon;
  title: string;
  body: string;
  href: string;
}[] = [
  {
    icon: ScalesIcon,
    title: "Assess a case",
    body:
      "Describe your situation or attach a document. See where you stand and what helps or hurts, weighed against how real Supreme Court cases were decided.",
    href: "/workspace?tab=assess",
  },
  {
    icon: ChatIcon,
    title: "Ask a question",
    body:
      "Ask any legal question and get a clear answer that cites the actual judgments behind it, so you can check the source yourself.",
    href: "/workspace?tab=ask",
  },
  {
    icon: BookIcon,
    title: "Find the law",
    body:
      "Pinpoint the Acts and sections that govern your situation, linked to the cases that interpret them.",
    href: "/workspace?tab=law",
  },
];

const STEPS = [
  { n: "01", t: "Describe", d: "Tell us your issue, or attach a document." },
  { n: "02", t: "We match", d: "We pull the Supreme Court cases closest to yours." },
  { n: "03", t: "Where you stand", d: "A clear read on your position, and the factors that help or hurt." },
  { n: "04", t: "What to do", d: "Practical next steps, with every cited case real and checkable." },
];

export default function Home() {
  return (
    <>
      <Nav />

      <section className="relative overflow-hidden">
        <div className="container-page flex min-h-[100svh] flex-col items-center justify-center gap-7 pb-24 pt-32 text-center lg:pb-28 lg:pt-36">
          <Reveal className="eyebrow">
            <GoldLine />Indian Supreme Court precedent
          </Reveal>

          <h1 className="flex max-w-4xl flex-col items-center gap-1">
            <MaskedTextReveal
              as="div"
              text="Legally AI."
              maskPad={14}
              className="justify-center font-serif text-[2.6rem] font-semibold leading-[1.15] tracking-[-0.02em] text-ink sm:text-6xl lg:text-[4.5rem]"
            />
            <MaskedTextReveal
              as="div"
              text="Your AI Paralegal."
              maskPad={14}
              delay={0.32}
              className="justify-center font-serif text-[2.6rem] font-semibold leading-[1.15] tracking-[-0.02em] text-gold-600 sm:text-6xl lg:text-[4.5rem]"
            />
          </h1>

          <Reveal as="p" delay={0.6}
            className="max-w-xl text-xl font-medium leading-snug text-ink/80">
            Real cases. Real odds. Real answers.
          </Reveal>

          <Reveal delay={0.75} className="flex flex-wrap items-center justify-center gap-3">
            <Link href="/workspace?tab=assess" className="btn-primary">
              Assess your case
              <ArrowIcon />
            </Link>
            <a href="#demo" className="btn-ghost">See the demo</a>
          </Reveal>
        </div>
      </section>

      <section id="capabilities" className="container-page py-20">
        <Reveal className="max-w-2xl">
          <span className="eyebrow"><GoldLine />What you can do</span>
          <h2 className="mt-4 font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            Three tools, one matter.
          </h2>
          <p className="mt-4 text-ink/65">
            Every answer traces back to a real judgment, not a guess.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3" gap={0.06}>
          {CAPABILITIES.map((c) => {
            const Icon = c.icon;
            return (
              <StaggerItem key={c.title}>
                <Link href={c.href} className="block h-full">
                  <div className="card group flex h-full flex-col transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-1 hover:shadow-lift">
                    <div className="flex items-center gap-3">
                      <Icon className="h-6 w-6 shrink-0 text-gold-600" />
                      <h3 className="font-serif text-xl font-semibold text-ink">{c.title}</h3>
                    </div>
                    <p className="mt-3 flex-1 text-sm leading-relaxed text-ink/65">{c.body}</p>
                    <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-gold-700">
                      Open
                      <ArrowIcon className="h-4 w-4" />
                    </span>
                  </div>
                </Link>
              </StaggerItem>
            );
          })}
        </Stagger>
      </section>

      <DashboardDemo />

      <section id="how" className="border-y border-ink/10 bg-navy-950 text-cream">
        <div className="container-page py-20">
          <Reveal className="max-w-2xl">
            <span className="eyebrow text-gold-400"><GoldLine className="h-px w-6 bg-gold-400" />How it works</span>
            <h2 className="mt-4 font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
              From your situation to an answer you can check.
            </h2>
          </Reveal>
          <Stagger className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-white/10 sm:grid-cols-2 lg:grid-cols-4" gap={0.08}>
            {STEPS.map((s) => (
              <StaggerItem key={s.n} className="bg-surface/[0.03] p-7">
                <div className="font-serif text-2xl text-gold-400">{s.n}</div>
                <div className="mt-3 text-lg font-semibold">{s.t}</div>
                <p className="mt-1.5 text-sm leading-relaxed text-cream/65">{s.d}</p>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="border-y border-ink/10 bg-surface/40 py-5">
        <div className="container-page mb-3">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink/40">
            Matters people bring to Legally AI
          </span>
        </div>
        <Marquee items={PRACTICE_AREAS} />
      </section>

      <section id="method" className="container-page py-20">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
          <Reveal>
            <span className="eyebrow"><GoldLine />The method</span>
            <h2 className="mt-4 font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              Three signals, and an honest confidence level.
            </h2>
            <p className="mt-5 leading-relaxed text-ink/70">
              Rather than trust a single model&apos;s guess, Legally AI weighs three independent
              signals and sets its confidence by how much they agree. When they disagree, it tells
              you, instead of sounding sure when it isn&apos;t.
            </p>
            <Stagger className="mt-6 space-y-4" gap={0.08}>
              {[
                ["Past cases", "How the most similar decided cases actually came out."],
                ["A trained model", "A model trained on thousands of past judgments to spot the likely outcome."],
                ["AI reasoning", "A careful read of the retrieved judgments, clearly explained."],
              ].map(([t, d]) => (
                <StaggerItem key={t} className="flex gap-3">
                  <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-navy-900 text-gold-400">
                    <ScalesIcon className="h-3.5 w-3.5" />
                  </span>
                  <span className="text-sm leading-relaxed text-ink/75">
                    <strong className="font-semibold text-ink">{t}.</strong> {d}
                  </span>
                </StaggerItem>
              ))}
            </Stagger>
          </Reveal>

          <Reveal delay={0.1} className="card">
            <div className="text-sm font-semibold uppercase tracking-wider text-ink/55">
              Agreement → confidence
            </div>
            <div className="mt-5 space-y-3">
              {[
                ["All signals agree", "high", 100],
                ["Two of three agree", "medium", 66],
                ["Signals diverge", "low", 33],
              ].map(([label, conf, w]) => (
                <div key={conf as string} className="rounded-xl border border-ink/10 bg-surface/60 p-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-ink/75">{label}</span>
                    <span className="font-semibold capitalize text-ink">{conf}</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink/10">
                    <MotionBar pct={w as number} className="h-full rounded-full bg-gold-500" />
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      <section className="container-page pb-8">
        <Reveal className="overflow-hidden rounded-3xl bg-navy-950 px-8 py-12 text-center text-cream shadow-lift sm:px-16">
          <h2 className="mx-auto max-w-2xl font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
            See where your case stands.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-cream/70">
            Describe what happened in a few sentences, or attach a document. It takes a minute.
          </p>
          <Link href="/workspace?tab=assess" className="btn-primary mt-8 bg-gold-500 text-navy-950 hover:bg-gold-400">
            Assess your case
            <ArrowIcon />
          </Link>
        </Reveal>
      </section>

      <Footer />
    </>
  );
}
