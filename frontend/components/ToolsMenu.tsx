"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ScalesIcon, ChatIcon, BookIcon } from "@/components/ui";

const TOOLS = [
  { href: "/workspace?tab=assess", name: "Assess a case", desc: "Predict, read docs & chat", icon: ScalesIcon },
  { href: "/workspace?tab=ask", name: "Ask a question", desc: "Chat grounded in precedent", icon: ChatIcon },
  { href: "/workspace?tab=law", name: "Find the law", desc: "Acts & sections that apply", icon: BookIcon },
];

export function ToolsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 transition hover:text-ink"
        aria-expanded={open}
      >
        Tools
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-1/2 top-full z-50 mt-3 w-72 -translate-x-1/2 rounded-2xl border border-ink/10 bg-surface/95 p-2 shadow-lift backdrop-blur">
          {TOOLS.map((t) => {
            const Icon = t.icon;
            return (
              <Link
                key={t.href}
                href={t.href}
                onClick={() => setOpen(false)}
                className="flex items-start gap-3 rounded-xl p-2.5 transition hover:bg-ink/5"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-navy-900 text-gold-400">
                  <Icon className="h-5 w-5" />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-ink">{t.name}</span>
                  <span className="block text-xs text-ink/55">{t.desc}</span>
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
