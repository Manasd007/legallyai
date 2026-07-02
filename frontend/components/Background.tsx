"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

/* Ambient background: a slow WebGL "color bends" wash (react-bits ColorBends,
   three.js) behind everything — gentle ribbons that drift on their own. The
   palette flips with the theme (warm gold in light, cool sage/jade in dark to
   match the dark accent). Non-interactive, behind content, and disabled under
   prefers-reduced-motion. */

// Client-only: three.js touches the GPU, so never render it on the server.
const ColorBends = dynamic(() => import("@/components/ColorBends"), { ssr: false });

export function Background() {
  const reduce = useReducedMotion();
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Mirror the app's `dark` class on <html> so we flip with the theme toggle.
  useEffect(() => {
    setMounted(true);
    const root = document.documentElement;
    const update = () => setIsDark(root.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  // Render in both themes; only skip under reduced motion / before mount.
  if (!mounted || reduce) return null;

  // Warm gold in light, cool sage/jade in dark (matches the dark accent ramp).
  const palette = isDark
    ? { colors: ["#9db2a3", "#b5c8bc", "#afc4b6"], noise: 0, intensity: 0.7 }
    : { colors: ["#bd9148", "#d4ad68", "#9e7634"], noise: 0.1, intensity: 1.1 };

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 opacity-40">
      <ColorBends
        rotation={90}
        speed={0.2}
        colors={palette.colors}
        transparent
        autoRotate={0}
        scale={0.9}
        frequency={1}
        warpStrength={1}
        mouseInfluence={0.3}
        parallax={0.5}
        noise={palette.noise}
        iterations={1}
        intensity={palette.intensity}
        bandWidth={4}
      />
    </div>
  );
}
