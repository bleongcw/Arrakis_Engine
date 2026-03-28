"use client";

import { PlayerSelector } from "./player-selector";
import { ThemeToggle } from "./theme-toggle";

export function AppHeader() {
  return (
    <header className="border-b border-border bg-card">
      <div className="max-w-7xl mx-auto px-3 sm:px-4 h-14 flex items-center justify-between gap-2">
        <h1 className="text-base sm:text-lg font-bold text-[#333] dark:text-gray-100 shrink-0">
          <span className="italic">Arrakis</span> Engine
        </h1>
        <div className="flex items-center gap-2 sm:gap-3">
          <PlayerSelector />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
