import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/app-header";
import { NavBar } from "@/components/nav-bar";

export const metadata: Metadata = {
  title: "Arrakis Engine",
  description: "Chess Coach AI — powered by Stockfish and LLMs",
};

// v1.18.2: the viewport meta tag. Without it, mobile browsers render
// the page at desktop width and zoom out, so the responsive `sm:`/
// `md:`/`lg:` breakpoints never trigger. Next.js 16 injects
// `<meta name="viewport" content="width=device-width, initial-scale=1">`
// from this export. We deliberately do NOT set maximumScale /
// userScalable=false — locking pinch-zoom is an accessibility
// anti-pattern, and a 9-year-old may genuinely want to zoom the board.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground font-sans" suppressHydrationWarning>
        <Providers>
          <AppHeader />
          <NavBar />
          <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
