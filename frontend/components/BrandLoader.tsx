"use client";

import { ScalesIcon } from "@/components/ui";

/* A consistent, on-brand loading indicator: the scales of justice held inside a
   spinning gold arc, with a label and a soft pulsing trail. Used for any action
   that runs for more than a moment (predicting, analysing, finding statutes). */

export function BrandLoader({
  label,
  sub,
  size = "md",
}: {
  label?: string;
  sub?: string;
  size?: "sm" | "md";
}) {
  const ring = size === "sm" ? "h-12 w-12" : "h-16 w-16";
  const icon = size === "sm" ? "h-5 w-5" : "h-7 w-7";
  return (
    <div className="flex flex-col items-center justify-center text-center">
      <div className={`relative ${ring}`}>
        {/* track */}
        <div className="absolute inset-0 rounded-full border-2 border-ink/10" />
        {/* spinning gold arc */}
        <div
          className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-gold-500 border-r-gold-400/70"
          style={{ animationDuration: "0.85s" }}
        />
        {/* scales, gently breathing */}
        <span className="absolute inset-0 grid place-items-center text-gold-600">
          <span className="animate-pulse">
            <ScalesIcon className={icon} />
          </span>
        </span>
      </div>

      {label && <p className="mt-4 text-sm font-medium text-ink/75">{label}</p>}
      {sub && <p className="mt-1 text-xs text-ink/45">{sub}</p>}

      <span className="mt-3 flex gap-1.5" aria-hidden>
        {[0, 0.15, 0.3].map((d) => (
          <span
            key={d}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-gold-500/70"
            style={{ animationDelay: `${d}s` }}
          />
        ))}
      </span>
    </div>
  );
}
