"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface TimeControlData {
  [key: string]: {
    games: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
    acpl: number;
    blunders: number;
    blunder_rate: number;
  };
}

const TC_ORDER = ["bullet", "blitz", "rapid", "daily", "unknown"];
const TC_ICONS: Record<string, string> = {
  bullet: "⚡",
  blitz: "🔥",
  rapid: "⏱️",
  daily: "📅",
  unknown: "❓",
};

function InfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Time Controls</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Breaks down your results by time control format. Rows are highlighted green (best) and red (weakest) by win rate.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>ACPL</strong> — Average Centipawn Loss. Lower = more accurate play.</li>
          <li><strong>Blunder%</strong> — Percentage of moves that were blunders (300cp+ loss). Above 10% is concerning.</li>
          <li><strong>W/L/D</strong> — Wins / Losses / Draws breakdown.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Faster time controls (bullet, blitz) typically have higher ACPL due to time pressure.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function TimeControlPerformance({ data }: { data: TimeControlData }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const sorted = Object.entries(data)
    .sort(([a], [b]) => TC_ORDER.indexOf(a) - TC_ORDER.indexOf(b))
    .filter(([, v]) => v.games > 0);

  // Find best/worst time control
  const best = sorted.reduce((a, b) => (a[1].win_rate > b[1].win_rate ? a : b));
  const worst = sorted.reduce((a, b) => (a[1].win_rate < b[1].win_rate ? a : b));

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Time Control Performance
        </h3>
        <button
          onClick={() => setShowInfo(true)}
          className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          title="What do these columns mean?"
        >&#9432;</button>
      </div>
      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground uppercase tracking-wider">
              <th className="pb-2 font-medium">Format</th>
              <th className="pb-2 font-medium text-right">Games</th>
              <th className="pb-2 font-medium text-right">Win%</th>
              <th className="pb-2 font-medium text-right">W/L/D</th>
              <th className="pb-2 font-medium text-right">ACPL</th>
              <th className="pb-2 font-medium text-right">Blunder%</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(([tc, d]) => {
              const isBest = tc === best[0] && sorted.length > 1;
              const isWorst = tc === worst[0] && sorted.length > 1;
              return (
                <tr
                  key={tc}
                  className={`border-b last:border-0 ${
                    isBest
                      ? "bg-green-50 dark:bg-green-950/30"
                      : isWorst
                        ? "bg-red-50 dark:bg-red-950/30"
                        : ""
                  }`}
                >
                  <td className="py-2.5 font-medium">
                    {TC_ICONS[tc] || ""} {tc.charAt(0).toUpperCase() + tc.slice(1)}
                    {isBest && (
                      <span className="ml-2 text-[10px] text-green-600 dark:text-green-400 font-semibold">
                        BEST
                      </span>
                    )}
                    {isWorst && (
                      <span className="ml-2 text-[10px] text-red-500 font-semibold">
                        WEAKEST
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 text-right text-muted-foreground">
                    {d.games}
                  </td>
                  <td className="py-2.5 text-right font-semibold">
                    {d.win_rate}%
                  </td>
                  <td className="py-2.5 text-right text-xs text-muted-foreground">
                    {d.wins}/{d.losses}/{d.draws}
                  </td>
                  <td className="py-2.5 text-right">
                    {d.acpl > 0 ? d.acpl : "—"}
                  </td>
                  <td className="py-2.5 text-right">
                    <span
                      className={
                        d.blunder_rate > 10
                          ? "text-red-500 font-medium"
                          : d.blunder_rate > 5
                            ? "text-orange-500"
                            : "text-muted-foreground"
                      }
                    >
                      {d.blunder_rate}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
