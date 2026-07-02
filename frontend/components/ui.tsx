import Link from "next/link";
import { Scale, Gauge, ShieldCheck, FileText, MessageSquare, BookOpen, ArrowRight } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import CardNav, { type CardNavItem } from "@/components/CardNav";

/* ---------------------------------- Icons --------------------------------- */
/* Industry-standard Lucide icons, re-exported under the app's existing names so
 call sites are unchanged. Stroke 1.6 to match the refined, editorial feel. */

type IconProps = { className?: string };
const base = "h-6 w-6";

// Function declarations (not const) so they stay hoisted, ui.tsx <-> ToolsMenu/
// MobileMenu form a small import cycle and const arrows would hit the TDZ.
export function ScalesIcon({ className = base }: IconProps) {
 return <Scale className={className} strokeWidth={1.6} aria-hidden />;
}
export function GaugeIcon({ className = base }: IconProps) {
 return <Gauge className={className} strokeWidth={1.6} aria-hidden />;
}
export function ShieldCheckIcon({ className = base }: IconProps) {
 return <ShieldCheck className={className} strokeWidth={1.6} aria-hidden />;
}
export function DocIcon({ className = base }: IconProps) {
 return <FileText className={className} strokeWidth={1.6} aria-hidden />;
}
export function ChatIcon({ className = base }: IconProps) {
 return <MessageSquare className={className} strokeWidth={1.6} aria-hidden />;
}
export function BookIcon({ className = base }: IconProps) {
 return <BookOpen className={className} strokeWidth={1.6} aria-hidden />;
}
export function ArrowIcon({ className = "h-4 w-4" }: IconProps) {
 return <ArrowRight className={className} strokeWidth={1.8} aria-hidden />;
}

/* ---------------------------------- Badge --------------------------------- */

export function StatusBadge({ status }: { status: "available" | "soon" }) {
 if (status === "available") {
 return (
 <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink">
 <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
 Available
 </span>
 );
 }
 return (
 <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink/55">
 <span className="h-1.5 w-1.5 rounded-full bg-gold-500" />
 Coming soon
 </span>
 );
}

/* ----------------------------------- Logo --------------------------------- */

export function Logo({
 withText = true,
 textClassName = "text-lg",
}: {
 withText?: boolean;
 textClassName?: string;
}) {
 return (
 <Link href="/" className="group inline-flex items-center gap-2.5">
 {withText && (
 <span className={`font-serif ${textClassName} font-semibold tracking-tight text-ink`}>
 Legally<span className="text-gold-600">AI</span>
 </span>
 )}
 </Link>
 );
}

/* ----------------------------------- Nav ---------------------------------- */

// Warm-neutral palette (Harvey-style). Light = warm near-black editorial cards
// on ivory; dark = elevated graphite on warm near-black, with an amber spark.
const NAV_ITEMS: CardNavItem[] = [
  {
    label: "Tools",
    bgColor: "#161618", // charcoal (navy-900)
    textColor: "#f4f1ea", // cream
    bgColorDark: "#1c1c1e", // elevated neutral grey
    textColorDark: "#ededed",
    links: [
      { label: "Assess a case", href: "/workspace?tab=assess", ariaLabel: "Assess a case" },
      { label: "Ask a question", href: "/workspace?tab=ask", ariaLabel: "Ask a question" },
      { label: "Find the law", href: "/workspace?tab=law", ariaLabel: "Find the law" },
    ],
  },
  {
    label: "Learn",
    bgColor: "#1e1e21", // charcoal (navy-800)
    textColor: "#f4f1ea",
    bgColorDark: "#232326",
    textColorDark: "#ededed",
    links: [
      { label: "How it works", href: "/#how", ariaLabel: "How it works" },
      { label: "The method", href: "/#method", ariaLabel: "The method" },
    ],
  },
  {
    label: "Get started",
    bgColor: "#2a2a2d", // charcoal (navy-700)
    textColor: "#f4f1ea",
    bgColorDark: "#2a2a2d",
    textColorDark: "#ededed",
    links: [
      { label: "Assess your case", href: "/workspace?tab=assess", ariaLabel: "Assess your case" },
    ],
  },
];

export function Nav() {
  return (
    <CardNav
      logo={
        <span className="font-serif text-2xl font-semibold tracking-tight text-ink">
          Legally<span className="text-gold-500">AI</span>
        </span>
      }
      items={NAV_ITEMS}
      baseColor="#fbfaf6" // ivory surface (light stays warm)
      menuColor="#161618"
      buttonBgColor="#161618" // dark CTA on light
      buttonTextColor="#f4f1ea"
      baseColorDark="#18181a" // neutral grey surface
      menuColorDark="#ededed"
      buttonBgColorDark="#fafafa" // near-white CTA (Harvey-style)
      buttonTextColorDark="#0b0b0c"
      buttonLabel="Assess your case"
      buttonHref="/workspace?tab=assess"
      ease="power3.out"
      rightContent={<ThemeToggle />}
    />
  );
}

/* ---------------------------------- Footer -------------------------------- */

export function Footer() {
 return (
 <footer className="mt-24 border-t border-ink/10">
 <div className="container-page flex flex-col gap-6 py-10 text-sm text-ink/60 sm:flex-row sm:items-center sm:justify-between">
 <div className="flex items-center gap-2.5">
 <Logo />
 </div>
 <p className="max-w-md leading-relaxed">
 Built on public Indian Supreme Court judgments (CC-BY-4.0).
 </p>
 <p className="text-xs text-ink/45">© {new Date().getFullYear()} Legally AI</p>
 </div>
 </footer>
 );
}
