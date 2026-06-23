"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { cn } from "@/lib/utils";

// Shape of a nav entry. Exported so out-of-tree consumers (e.g. the
// commercial Atreides build's PGN-import page) can compose their own
// entries to pass via <NavBar extraItems> without forking this file.
export type NavItem = {
  href: string;
  label: string;
  playerScoped: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", playerScoped: false },
  { href: "/games", label: "Games", playerScoped: true },
  // v1.24.0: Import a PGN (paste/upload) → analyzed game.
  { href: "/import", label: "Import", playerScoped: true },
  { href: "/patterns", label: "Patterns", playerScoped: true },
  // v1.10.0: Journal — chronological diary of LLM coaching reviews
  // (and v1.12.0+ parent-authored notes). Sits between Patterns (stats
  // overview) and Hunt (opponent prep) as the narrative companion to Patterns.
  { href: "/journal", label: "Journal", playerScoped: true },
  { href: "/hunt", label: "Hunt", playerScoped: true },
  // v1.21.0: Tournament Prep — multi-opponent rosters built on Hunt.
  { href: "/tournament", label: "Tournament", playerScoped: true },
  { href: "/reports", label: "Reports", playerScoped: true },
];

export function NavBar({ extraItems = [] }: { extraItems?: NavItem[] }) {
  const pathname = usePathname();
  const { currentPlayer } = usePlayerContext();

  return (
    <nav className="border-b border-border bg-card">
      {/* v1.24.1: wrap instead of single-row horizontal scroll. The nav grew
          to 8 items (Import added v1.24.0); a hidden-scrollbar overflow row was
          pushing the last items (Tournament, Reports) off-screen with no cue
          they were there. Wrapping keeps every item reachable at any width. */}
      <div className="max-w-7xl mx-auto px-2 sm:px-4 flex flex-wrap gap-y-1">
        {[...NAV_ITEMS, ...extraItems].map(({ href, label, playerScoped }) => {
          const fullHref = playerScoped && currentPlayer
            ? `/${currentPlayer}${href}`
            : href;

          // Active detection: match /<player>/games or /dashboard
          const isActive = playerScoped
            ? pathname.includes(href)
            : pathname === href;

          return (
            <Link
              key={href}
              href={fullHref}
              className={cn(
                "px-3 sm:px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                isActive
                  ? "border-[#1e40af] text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
