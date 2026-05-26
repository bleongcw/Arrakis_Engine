"use client";

import { type ReactNode } from "react";

/** v1.11.0: Sticky section header for a day-grouped batch of Journal entries.
 *
 * Sits above the entries it labels, integrated with the vertical timeline rail
 * so the line passes through cleanly. Sticks to the top of the viewport while
 * the user scrolls that bucket, then releases when the next bucket starts. */

export interface DayGroupProps {
  label: string;
  count: number;
  children: ReactNode;
}

export function DayGroup({ label, count, children }: DayGroupProps) {
  return (
    <section className="space-y-3">
      <header
        className={
          // Sticky to the top so the bucket label stays in view while scrolling
          // through its entries. `top-0` is intentional — the page itself
          // doesn't have a sticky nav competing for that slot inside the feed.
          "sticky top-0 z-10 -mx-2 px-2 py-1 bg-background/95 backdrop-blur " +
          "border-b border-border/40 flex items-baseline gap-2"
        }
      >
        <h3 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">
          {label}
        </h3>
        <span className="text-[10px] text-muted-foreground/70">
          · {count} {count === 1 ? "entry" : "entries"}
        </span>
      </header>
      {/* Entries live inside this region so the sticky header releases them
          when the next group's header appears */}
      <div className="space-y-3">{children}</div>
    </section>
  );
}
