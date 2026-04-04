"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface CriticalPositionsData {
  total_critical: number;
  handled_well: number;
  success_rate: number;
  opportunities_found: number;
  opportunities_total: number;
  opportunity_rate: number;
}

function Gauge({ value, label, color }: { value: number; label: string; color: string }) {
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor"
          className="text-muted/30" strokeWidth="8" />
        <circle cx="50" cy="50" r="40" fill="none" stroke={color}
          strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform="rotate(-90 50 50)" className="transition-all duration-700" />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
          className="fill-foreground text-lg font-bold">{value}%</text>
      </svg>
      <span className="text-xs text-muted-foreground mt-1 text-center">{label}</span>
    </div>
  );
}

function CriticalInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Critical Positions</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Measures performance in high-stakes moments where a &gt;200 centipawn swing was possible:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Under Pressure</strong> — You&apos;re in a critical position. Did you find a good move? Green = 50%+, yellow = 25-50%, red = below 25%.</li>
          <li><strong>Capitalizing</strong> — Your opponent blundered. Did you take advantage? Higher is better — above 60% is strong.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Improving these gauges means better calculation and pattern recognition under pressure.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function CriticalPositions({ data }: { data: CriticalPositionsData }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data || data.total_critical === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Critical Positions
        </h3>
        <button onClick={() => setShowInfo(true)} className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors" title="What are critical positions?">&#9432;</button>
      </div>
      {showInfo && <CriticalInfoModal onClose={() => setShowInfo(false)} />}
      <p className="text-xs text-muted-foreground mb-4">
        How well you handle high-pressure moments and capitalize on opponent mistakes.
      </p>

      <div className="flex justify-around">
        <Gauge
          value={data.success_rate}
          label={`Under Pressure\n(${data.handled_well}/${data.total_critical})`}
          color={data.success_rate >= 50 ? "#22c55e" : data.success_rate >= 25 ? "#eab308" : "#ef4444"}
        />
        <Gauge
          value={data.opportunity_rate}
          label={`Capitalizing\n(${data.opportunities_found}/${data.opportunities_total})`}
          color={data.opportunity_rate >= 60 ? "#22c55e" : data.opportunity_rate >= 40 ? "#eab308" : "#ef4444"}
        />
      </div>

      <div className="mt-4 pt-3 border-t text-xs text-muted-foreground space-y-1">
        <p><strong>Under Pressure:</strong> % of critical moments (&gt;200cp swing possible) where you found a good move</p>
        <p><strong>Capitalizing:</strong> % of opponent blunders where you took advantage</p>
      </div>
    </div>
  );
}
