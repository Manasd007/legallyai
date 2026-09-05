"use client";

import { useEffect } from "react";





type LenisLike = { stop: () => void; start: () => void } | null;

let lenis: LenisLike = null;
let lockCount = 0;
let savedOverflow = "";
let savedPaddingRight = "";

export function registerLenis(instance: LenisLike) {
  lenis = instance;
  if (lockCount > 0) lenis?.stop();
}

function applyLock() {
  if (typeof document === "undefined") return;
  const { body } = document;
  savedOverflow = body.style.overflow;
  savedPaddingRight = body.style.paddingRight;
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

export function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    lockScroll();
    return () => unlockScroll();
  }, [active]);
}
