"use client";

import type { ComponentType, ReactNode } from "react";

type IconType = ComponentType<{ className?: string }>;


export type IntroExample = { label: string; onClick: () => void };

export function TabIntro({
  icon: Icon,
  title,
  subtitle,
  composer,
  notice,
  matter,
  onUseMatter,
  examples,
}: {
  icon: IconType;
  title: string;
  subtitle: string;
  composer: ReactNode;
  notice?: ReactNode;
  matter?: string | null;
  onUseMatter?: () => void;
  examples?: IntroExample[];
}) {
  return (
    <div className="mx-auto w-full max-w-2xl px-1 pb-16 pt-[7vh] sm:pt-[11vh]">
      <div className="flex flex-col items-center text-center">
        <span className="grid h-12 w-12 place-items-center rounded border-2 border-ink bg-navy-900 text-gold-400 shadow-brutal-sm">
          <Icon className="h-6 w-6" />
        </span>
        <h2 className="mt-5 font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          {title}
        </h2>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-ink/60">{subtitle}</p>
      </div>

      <div className="mt-7">{composer}</div>

      {notice}

      {matter && onUseMatter && (
        <button
          onClick={onUseMatter}
          className="mt-4 block w-full rounded border-2 border-gold-500/60 bg-gold-400/10 px-4 py-3 text-left text-sm transition hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-brutal-gold"
        >
          <span className="block font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-gold-700">
            Continue your matter
          </span>
          <span className="mt-0.5 line-clamp-2 text-ink/70">{matter}</span>
        </button>
      )}

      {examples && examples.length > 0 && (
        <div className="mt-6">
          <p className="mb-2.5 text-center font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-ink/40">
            Try an example
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {examples.map((ex) => (
              <button
                key={ex.label}
                onClick={ex.onClick}
                className="rounded border-2 border-ink/25 bg-surface/50 px-3.5 py-1.5 text-left text-xs text-ink/65 backdrop-blur-sm transition hover:border-ink hover:text-ink"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
