"use client";

import { useEffect } from "react";

/* Central scroll lock for overlays (modals, drawers, full-screen loaders).

   Why this exists: the app drives the page with Lenis smooth scroll wired to the
   window (see SmoothScroll). Lenis listens to wheel/touch at the window level and
   translates them into a programmatic scroll, so the usual `body { overflow:hidden }`
   trick does NOT stop the page moving underneath an overlay. The only reliable way
   is to call `lenis.stop()` while an overlay is open (and `start()` when it closes).

   Lenis is registered once near the root, but some overlays (e.g. RouteLoader) live
   OUTSIDE the React provider, so we keep the instance in a module singleton instead
   of relying on the useLenis context.

   Locks are ref-counted so several overlays can be open at once without one of them
   prematurely re-enabling scrolling for the others. Inner scroll areas should also
   carry `data-lenis-prevent` so they scroll natively while the page stays put. */

type LenisLike = { stop: () => void; start: () => void } | null;

let lenis: LenisLike = null;
let lockCount = 0;
let savedOverflow = "";
let savedPaddingRight = "";

export function registerLenis(instance: LenisLike) {
  lenis = instance;
  // If something is already locked when Lenis (re)registers, keep it stopped.
  if (lockCount > 0) lenis?.stop();
}

function applyLock() {
  if (typeof document === "undefined") return;
  const { body } = document;
  savedOverflow = body.style.overflow;
  savedPaddingRight = body.style.paddingRight;
  // Compensate for the disappearing scrollbar so the layout doesn't shift.
  const scrollbar = window.innerWidth - document.documentElement.clientWidth;
  body.style.overflow = "hidden";
  if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
  lenis?.stop();
}

function releaseLock() {
  if (typeof document === "undefined") return;
  const { body } = document;
  body.style.overflow = savedOverflow;
  body.style.paddingRight = savedPaddingRight;
  lenis?.start();
}

export function lockScroll() {
  lockCount += 1;
  if (lockCount === 1) applyLock();
}

export function unlockScroll() {
  if (lockCount === 0) return;
  lockCount -= 1;
  if (lockCount === 0) releaseLock();
}

/* Lock the page scroll for as long as `active` is true. Safe to mount/unmount;
   the lock is always released on cleanup. */
export function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    lockScroll();
    return () => unlockScroll();
  }, [active]);
}
