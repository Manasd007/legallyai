"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/ui";
import { ThemeToggle } from "@/components/ThemeToggle";
import { BrandLoader } from "@/components/BrandLoader";
import { useSession } from "@/components/session";
import { useAuth } from "@/components/auth";
import { AccountPanel, HistoryPanel } from "@/components/SidebarHistory";
import { useScrollLock } from "@/components/scrollLock";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
 const pathname = usePathname();
 const router = useRouter();
 const { user, ready, enabled } = useAuth();
 const [open, setOpen] = useState(false);

 useScrollLock(open);

 useEffect(() => {
 setOpen(false);
 }, [pathname]);

 useEffect(() => {
 if (enabled && ready && !user) {
 router.replace(`/login?next=${encodeURIComponent(pathname)}`);
 }
 }, [enabled, ready, user, pathname, router]);

 if (enabled && (!ready || !user)) {
 return (
 <div className="grid min-h-screen place-items-center">
 <BrandLoader />
 </div>
 );
 }

 return (
 <div className="min-h-screen">
 <div className="sticky top-0 z-40 flex items-center justify-between border-b-2 border-ink bg-parchment/85 px-4 py-3 backdrop-blur-md lg:hidden">
 <Logo withText textClassName="text-2xl" />
 <div className="flex items-center gap-2">
 <ThemeToggle />
 <button
 onClick={() => setOpen(true)}
 aria-label="Open workspace menu"
 className="grid h-9 w-9 place-items-center rounded border-2 border-ink bg-surface/60 text-ink/70"
 >
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
 strokeLinecap="round" className="h-5 w-5" aria-hidden>
 <path d="M4 6h16M4 12h16M4 18h16" />
 </svg>
 </button>
 </div>
 </div>

 <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col border-r-2 border-ink bg-surface/55 backdrop-blur-md lg:flex">
 <SidebarContent />
 </aside>

 {open && (
 <div className="fixed inset-0 z-50 lg:hidden">
 <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={() => setOpen(false)} />
 <aside data-lenis-prevent className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col overflow-y-auto border-r-2 border-ink bg-parchment shadow-lift">
 <SidebarContent onNavigate={() => setOpen(false)} />
 </aside>
 </div>
 )}

      <div className="relative min-h-screen lg:pl-72">
        <div
          aria-hidden
          className="pointer-events-none fixed inset-y-0 left-0 right-0 z-0 bg-parchment/30 backdrop-blur-[10px] lg:left-72"
        />
        <div className="relative z-[1]">{children}</div>
      </div>
 </div>
 );
}

function SidebarContent({
 onNavigate,
}: {
 onNavigate?: () => void;
}) {
 return (
 <div className="flex h-full flex-col gap-5 p-5">
 <div className="flex items-center justify-between">
 <Logo withText textClassName="text-2xl" />
 <span className="hidden lg:block">
 <ThemeToggle />
 </span>
 </div>

 <MatterPanel onNavigate={onNavigate} />

 <HistoryPanel onNavigate={onNavigate} />

 <div className="mt-auto flex flex-col gap-2">
 <AccountPanel onNavigate={onNavigate} />
 <Link
 href="/"
 onClick={onNavigate}
 className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-ink/55 transition hover:text-ink"
 >
 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
 strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
 <path d="M19 12H5M12 19l-7-7 7-7" />
 </svg>
 Back to home
 </Link>
 </div>
 </div>
 );
}

function MatterPanel({ onNavigate }: { onNavigate?: () => void }) {
 const router = useRouter();
 const { matter, newSession, ready } = useSession();

 if (!ready) {
 return <div className="h-20 animate-pulse rounded border-2 border-ink/10 bg-ink/5" />;
 }

 if (!matter) {
 return (
 <div className="rounded border-2 border-dashed border-ink/25 bg-surface/40 p-3.5 text-xs leading-relaxed text-ink/55">
 <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/70">No matter yet</div>
 <p className="mt-1">Describe your situation in any tab and it will follow you across the session.</p>
 </div>
 );
 }

 function reset() {
 newSession();
 router.push("/workspace/assess");
 onNavigate?.();
 }

 return (
 <div className="rounded border-2 border-gold-500/60 bg-gold-400/[0.08] p-3.5">
 <div className="flex items-center justify-between">
 <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-gold-700">
 Your matter
 </span>
 <button
 onClick={reset}
 className="text-[11px] font-medium text-ink/45 transition hover:text-ink/80"
 >
 New
 </button>
 </div>
 <p className="mt-1.5 line-clamp-4 text-xs leading-relaxed text-ink/75">{matter}</p>
 </div>
 );
}
