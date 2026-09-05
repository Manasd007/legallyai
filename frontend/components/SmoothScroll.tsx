"use client";

import { ReactLenis, useLenis } from "lenis/react";
import { useReducedMotion } from "framer-motion";
import { useEffect, type ReactNode } from "react";
import { registerLenis } from "@/components/scrollLock";

export function SmoothScroll({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();

  return (
    <ReactLenis
      root
      options={{
        lerp: 0.09,
        smoothWheel: !reduce,
        wheelMultiplier: 1,
        touchMultiplier: 1.6,
        syncTouch: false,
        anchors: { offset: -80 },
      }}
    >
      <LenisBridge />
      {children}
    </ReactLenis>
  );
}

function LenisBridge() {
  const lenis = useLenis();
  useEffect(() => {
    registerLenis(lenis ?? null);
    return () => registerLenis(null);
  }, [lenis]);
  return null;
}
