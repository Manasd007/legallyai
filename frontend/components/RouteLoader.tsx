"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BrandLoader } from "@/components/BrandLoader";
import { useScrollLock } from "@/components/scrollLock";

/* Smooth feedback for client-side navigations (switching workspace tools, etc.).
 App Router gives no transition events, so we start on an internal link click and
 finish when the pathname actually changes, i.e. when the next route is ready.
 A slim gold top bar always shows; a subtle branded overlay only appears if the
 navigation takes a beat, and stays a touch longer so it never flickers. */

const OVERLAY_DELAY = 170; // ms before the centered loader appears
const MIN_OVERLAY = 360; // ms it stays once shown, to avoid a flash
const SAFETY = 12000; // ms hard stop if a navigation never resolves

export function RouteLoader() {
 const pathname = usePathname();
 const [active, setActive] = useState(false); // top bar
 const [overlay, setOverlay] = useState(false); // centered loader
 const startedAt = useRef(0);
 const delayT = useRef<ReturnType<typeof setTimeout>>();
 const minT = useRef<ReturnType<typeof setTimeout>>();
 const safetyT = useRef<ReturnType<typeof setTimeout>>();

 // While the centered overlay is up, freeze the page so a slow navigation can't
 // be scrolled behind the loader.
 useScrollLock(overlay);

 // Finish whenever the route resolves.
 useEffect(() => {
 finish();
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [pathname]);

 // Begin on a left-click of an internal link.
 useEffect(() => {
 function onClick(e: MouseEvent) {
 if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
 return;
 const a = (e.target as HTMLElement | null)?.closest("a");
 if (!a) return;
 const href = a.getAttribute("href");
 const target = a.getAttribute("target");
 if (!href || (target && target !== "_self")) return;
 // Only same-app, non-anchor navigations.
 if (!href.startsWith("/") || href.startsWith("//")) return;
 const dest = href.split("#")[0];
 if (!dest || dest === pathname) return; // same page / pure hash
 begin();
 }
 document.addEventListener("click", onClick, true);
 return () => document.removeEventListener("click", onClick, true);
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [pathname]);

 function begin() {
 clearTimers();
 startedAt.current = Date.now();
 setActive(true);
 delayT.current = setTimeout(() => setOverlay(true), OVERLAY_DELAY);
 safetyT.current = setTimeout(finish, SAFETY);
 }

 function finish() {
 clearTimeout(delayT.current);
 clearTimeout(safetyT.current);
 setActive(false);
 const shownFor = Date.now() - startedAt.current;
 setOverlay((wasShown) => {
 if (wasShown) {
 // keep it up a touch so it reads as intentional, not a flicker
 minT.current = setTimeout(() => setOverlay(false), Math.max(0, MIN_OVERLAY - shownFor));
 return true;
 }
 return false;
 });
 }

 function clearTimers() {
 clearTimeout(delayT.current);
 clearTimeout(minT.current);
 clearTimeout(safetyT.current);
 }

 useEffect(() => clearTimers, []);

 return (
 <>
 {/* Top progress bar */}
 <div
 aria-hidden
 className={`pointer-events-none fixed inset-x-0 top-0 z-[100] h-[3px] transition-opacity duration-300 ${
 active ? "opacity-100" : "opacity-0"
 }`}
 >
 <div className="relative h-full w-full overflow-hidden bg-gold-500/15">
 <span
 className="absolute top-0 h-full rounded-full bg-gradient-to-r from-gold-600 via-gold-400 to-gold-500"
 style={{ animation: active ? "route-bar-slide 1.1s ease-in-out infinite" : "none" }}
 />
 </div>
 </div>

 {/* Subtle branded overlay for longer transitions */}
 <div
 aria-hidden={!overlay}
 className={`fixed inset-0 z-[99] grid place-items-center transition-opacity duration-300 ${
 overlay ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
 }`}
 style={{ visibility: overlay ? "visible" : "hidden" }}
 >
 <div className="absolute inset-0 bg-parchment/45 backdrop-blur-[2px]" />
 <div className="relative rounded-2xl border border-ink/10 bg-surface/85 px-8 py-7 shadow-lift">
 <BrandLoader label="One moment…" size="sm" />
 </div>
 </div>
 </>
 );
}
