"use client";

import { ReactLenis, useLenis } from "lenis/react";
import { useReducedMotion } from "framer-motion";
import { useEffect, type ReactNode } from "react";
import { registerLenis } from "@/components/scrollLock";

/* Lenis smooth scroll, wired to the native window scroll (root) so the sticky
   nav, anchors and framer-motion's whileInView keep working. Tuned for a
   natural, lag-free feel; smoothing is switched off under reduced-motion. */
export function SmoothScroll({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();

  return (
    <ReactLenis
      root
      options={{
        // Lower lerp = more inertia; this value reads as "natural", not floaty.
        lerp: 0.09,
        smoothWheel: !reduce,
        wheelMultiplier: 1,
        touchMultiplier: 1.6,
        // Native momentum on touch feels better than syncing it through Lenis.
        syncTouch: false,
        // Let Lenis own anchor jumps; offset clears the 64px sticky header.
        anchors: { offset: -80 },
      }}
    >
      <LenisBridge />
      {children}
    </ReactLenis>
  );
}

/* Hands the live Lenis instance to the scroll-lock module so overlays anywhere
   (even outside this provider, like RouteLoader) can stop/start the page. */
function LenisBridge() {
  const lenis = useLenis();
  useEffect(() => {
    registerLenis(lenis ?? null);
    return () => registerLenis(null);
  }, [lenis]);
  return null;
}
