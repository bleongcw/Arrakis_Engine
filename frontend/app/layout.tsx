import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/app-header";
import { NavBar } from "@/components/nav-bar";

export const metadata: Metadata = {
  title: "Arrakis Engine",
  description: "Chess Coach AI — powered by Stockfish and LLMs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground font-sans">
        <Providers>
          <AppHeader />
          <NavBar />
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
