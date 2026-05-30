"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", playerScoped: false },
  { href: "/games", label: "Games", playerScoped: true },
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

export function NavBar() {
  const pathname = usePathname();
  const { currentPlayer } = usePlayerContext();

  return (
    <nav className="border-b border-border bg-card">
      <div className="max-w-7xl mx-auto px-2 sm:px-4 flex gap-0 overflow-x-auto [&::-webkit-scrollbar]:hidden">
        {NAV_ITEMS.map(({ href, label, playerScoped }) => {
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
