"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BrandLoader } from "@/components/BrandLoader";
import { useScrollLock } from "@/components/scrollLock";


const OVERLAY_DELAY = 170;
const MIN_OVERLAY = 360;
const SAFETY = 12000;

export function RouteLoader() {
 const pathname = usePathname();
 const [active, setActive] = useState(false);
 const [overlay, setOverlay] = useState(false);
 const startedAt = useRef(0);
 const delayT = useRef<ReturnType<typeof setTimeout>>();
 const minT = useRef<ReturnType<typeof setTimeout>>();
 const safetyT = useRef<ReturnType<typeof setTimeout>>();

 useScrollLock(overlay);

 useEffect(() => {
 finish();
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [pathname]);

 useEffect(() => {
 function onClick(e: MouseEvent) {
 if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
 return;
 const a = (e.target as HTMLElement | null)?.closest("a");
 if (!a) return;
 const href = a.getAttribute("href");
 const target = a.getAttribute("target");
 if (!href || (target && target !== "_self")) return;
 if (!href.startsWith("/") || href.startsWith("//")) return;
 const dest = href.split("#")[0];
 if (!dest || dest === pathname) return;
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

 <div
 aria-hidden={!overlay}
 className={`fixed inset-0 z-[99] grid place-items-center transition-opacity duration-300 ${
 overlay ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
 }`}
 style={{ visibility: overlay ? "visible" : "hidden" }}
 >
 <div className="absolute inset-0 bg-parchment/45 backdrop-blur-[2px]" />
 <div className="relative rounded border-2 border-ink bg-surface/80 px-8 py-7 shadow-brutal-lg backdrop-blur-md">
 <BrandLoader label="One moment…" size="sm" />
 </div>
 </div>
 </>
 );
}
