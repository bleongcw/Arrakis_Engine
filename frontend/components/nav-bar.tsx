"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", playerScoped: false },
  { href: "/games", label: "Games", playerScoped: true },
  { href: "/patterns", label: "Patterns", playerScoped: true },
  { href: "/reports", label: "Reports", playerScoped: true },
];

export function NavBar() {
  const pathname = usePathname();
  const { currentPlayer } = usePlayerContext();

  return (
    <nav className="border-b border-border bg-card">
      <div className="max-w-7xl mx-auto px-4 flex gap-0">
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
                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
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
