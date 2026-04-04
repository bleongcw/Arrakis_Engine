"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface ComebackCollapseData {
  comebacks: {
    total_losing_games: number;
    recovered: number;
    won: number;
    drawn: number;
    comeback_rate: number;
  };
  collapses: {
    total_winning_games: number;
    collapsed: number;
    lost: number;
    drawn: number;
    collapse_rate: number;
  };
}

function MetricBar({
  label,
  value,
  total,
  rate,
  color,
  icon,
  detail,
}: {
  label: string;
  value: number;
  total: number;
  rate: number;
  color: string;
  icon: string;
  detail: string;
}) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">
          {icon} {label}
        </span>
        <span className="text-2xl font-bold" style={{ color }}>
          {rate}%
        </span>
      </div>
      <div className="w-full h-3 bg-muted rounded-full overflow-hidden mb-1">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(rate, 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{value} of {total} games</span>
        <span>{detail}</span>
      </div>
    </div>
  );
}

function ComebackInfoModal({ onClose }: { onClose: () => void }) {
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
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Resilience & Composure</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Measures your mental toughness in games where the evaluation swung by more than 200 centipawns:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Comeback Rate</strong> — Percentage of losing games (&gt;200cp behind) where you recovered to win or draw. Higher = more fighting spirit.</li>
          <li><strong>Collapse Rate</strong> — Percentage of winning games (&gt;200cp ahead) where you let the advantage slip. Lower = better composure.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          A high comeback rate with a low collapse rate shows strong mental resilience.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function ComebackCollapse({ data }: { data: ComebackCollapseData }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const cb = data.comebacks;
  const cl = data.collapses;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Resilience & Composure
        </h3>
        <button onClick={() => setShowInfo(true)} className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors" title="What does this measure?">&#9432;</button>
      </div>
      {showInfo && <ComebackInfoModal onClose={() => setShowInfo(false)} />}
      <p className="text-xs text-muted-foreground mb-4">
        How well you fight back from losing positions and hold winning ones.
      </p>

      <MetricBar
        label="Comeback Rate"
        value={cb.recovered}
        total={cb.total_losing_games}
        rate={cb.comeback_rate}
        color="#3b82f6"
        icon="💪"
        detail={`${cb.won}W ${cb.drawn}D`}
      />

      <MetricBar
        label="Collapse Rate"
        value={cl.collapsed}
        total={cl.total_winning_games}
        rate={cl.collapse_rate}
        color="#ef4444"
        icon="📉"
        detail={`${cl.lost}L ${cl.drawn}D`}
      />

      <div className="mt-3 pt-3 border-t text-xs text-muted-foreground space-y-1">
        <p><strong>Comeback:</strong> Was losing by &gt;200cp but recovered to win or draw</p>
        <p><strong>Collapse:</strong> Was winning by &gt;200cp but let it slip to a loss</p>
      </div>
    </div>
  );
}
