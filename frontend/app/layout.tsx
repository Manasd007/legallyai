import type { Metadata } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Background } from "@/components/Background";
import { SmoothScroll } from "@/components/SmoothScroll";
import { SessionProvider } from "@/components/session";
import { AuthProvider } from "@/components/auth";
import { RouteLoader } from "@/components/RouteLoader";

/* Headings (Satoshi) + body/subtext (Cabinet Grotesk) are loaded from
   Fontshare in <head> below; --font-serif / --font-sans are set in globals.css. */
const mono = IBM_Plex_Mono({
 subsets: ["latin"],
 weight: ["400", "500"],
 variable: "--font-mono",
 display: "swap",
});

export const metadata: Metadata = {
 title: "Legally AI — See where your case stands",
 description:
 "Predict and understand Indian legal outcomes grounded in real Supreme Court precedent. Every citation verified. A research tool, not legal advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
 return (
  <html lang="en" className={mono.variable} suppressHydrationWarning>
 <head>
 {/* Satoshi (headings) + Cabinet Grotesk (body/subtext) from Fontshare. */}
 <link rel="preconnect" href="https://api.fontshare.com" crossOrigin="anonymous" />
 <link
 rel="stylesheet"
 href="https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,700,900&f[]=cabinet-grotesk@400,500,700,800&display=swap"
 />
 {/* Set the theme before paint to avoid a flash of the wrong mode. */}
 <script
 dangerouslySetInnerHTML={{
 __html:
 "(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark');}}catch(e){}})();",
 }}
 />
 </head>
 <body>
 <Background />
 <RouteLoader />
 <AuthProvider>
 <SessionProvider>
 <SmoothScroll>{children}</SmoothScroll>
 </SessionProvider>
 </AuthProvider>
 </body>
 </html>
 );
}
