"use client";

import Link from "next/link";
import { useState } from "react";
import { ScalesIcon, ChatIcon, BookIcon, ArrowIcon } from "@/components/ui";
import { useScrollLock } from "@/components/scrollLock";

const TOOLS = [
  { href: "/workspace?tab=assess", name: "Assess a case", icon: ScalesIcon },
  { href: "/workspace?tab=ask", name: "Ask a question", icon: ChatIcon },
  { href: "/workspace?tab=law", name: "Find the law", icon: BookIcon },
];

export function MobileMenu() {
  const [open, setOpen] = useState(false);

  // Lock the page (and Lenis) while the menu is open.
  useScrollLock(open);

  return (
    <div className="md:hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        className="grid h-9 w-9 place-items-center rounded-lg border border-ink/15 bg-surface/60 text-ink/70 transition hover:text-ink"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" className="h-5 w-5" aria-hidden>
          {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
        </svg>
      </button>

      {open && (
        <div className="fixed inset-x-0 top-16 z-40 border-b border-ink/10 bg-parchment/95 backdrop-blur-md">
          <div className="container-page space-y-1 py-4">
            <div className="px-2 pb-1 text-xs font-semibold uppercase tracking-wider text-ink/45">Tools</div>
            {TOOLS.map((t) => {
              const Icon = t.icon;
              return (
                <Link
                  key={t.href}
                  href={t.href}
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-3 rounded-xl p-2.5 transition hover:bg-ink/5"
                >
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-navy-900 text-gold-400">
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="text-sm font-semibold text-ink">{t.name}</span>
                </Link>
              );
            })}

            <div className="flex gap-4 border-t border-ink/10 px-2 pt-3 text-sm text-ink/70">
              <a href="/#how" onClick={() => setOpen(false)} className="hover:text-ink">How it works</a>
              <a href="/#method" onClick={() => setOpen(false)} className="hover:text-ink">The method</a>
            </div>

            <Link href="/workspace?tab=assess" onClick={() => setOpen(false)} className="btn-primary mt-2 w-full">
              Assess your case
              <ArrowIcon />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
