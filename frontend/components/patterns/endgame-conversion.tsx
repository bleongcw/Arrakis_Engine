"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

interface EndgameConversionData {
  winning_endgames: {
    total: number;
    converted: number;
    drawn: number;
    lost: number;
    conversion_rate: number;
  };
  losing_endgames: {
    total: number;
    saved: number;
    drawn: number;
    lost: number;
    save_rate: number;
  };
  equal_endgames: {
    total: number;
    won: number;
    drawn: number;
    lost: number;
    win_rate: number;
  };
  games_reaching_endgame: number;
  total_analyzed: number;
  endgame_reach_pct: number;
}

function ProgressBar({
  value,
  color,
  label,
}: {
  value: number;
  color: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-20 text-xs text-muted-foreground text-right">
        {label}
      </div>
      <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.min(value, 100)}%`, backgroundColor: color }}
        />
      </div>
      <div className="w-14 text-sm font-semibold text-right">{value}%</div>
    </div>
  );
}

function StatRow({
  label,
  won,
  drawn,
  lost,
  total,
}: {
  label: string;
  won: number;
  drawn: number;
  lost: number;
  total: number;
}) {
  if (total === 0) return null;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-8 text-right text-muted-foreground">{total}</span>
      <span className="w-16 text-muted-foreground">{label}</span>
      <span className="text-green-600 dark:text-green-400">{won}W</span>
      <span className="text-muted-foreground">{drawn}D</span>
      <span className="text-red-500">{lost}L</span>
    </div>
  );
}

function EndgameInfoModal({ onClose }: { onClose: () => void }) {
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
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Endgame Conversion</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Measures how well you finish games based on your position at move 30:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#22c55e] mr-1.5" />
            <strong>Winning</strong> — Had &gt;200cp advantage. Did you convert to a win?</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#3b82f6] mr-1.5" />
            <strong>Losing</strong> — Had &gt;200cp disadvantage. Did you save/draw?</li>
          <li><span className="inline-block w-2 h-2 rounded-full bg-[#eab308] mr-1.5" />
            <strong>Equal</strong> — Within ±200cp. Did you outplay your opponent?</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          High conversion rate = strong technique. High save rate = great fighting spirit.
        </p>
      </div>
    </div>,
    document.body
  );
}

export function EndgameConversion({ data }: { data: EndgameConversionData }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data || data.total_analyzed === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const w = data.winning_endgames;
  const l = data.losing_endgames;
  const e = data.equal_endgames;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Endgame Conversion
        </h3>
        <button onClick={() => setShowInfo(true)} className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors" title="What is endgame conversion?">&#9432;</button>
      </div>
      {showInfo && <EndgameInfoModal onClose={() => setShowInfo(false)} />}
      <p className="text-xs text-muted-foreground mb-4">
        {data.games_reaching_endgame} of {data.total_analyzed} games reach the
        endgame ({data.endgame_reach_pct}%)
      </p>

      <div className="space-y-4">
        <div>
          <ProgressBar
            value={w.conversion_rate}
            color="#22c55e"
            label="Winning"
          />
          <StatRow
            label=""
            won={w.converted}
            drawn={w.drawn}
            lost={w.lost}
            total={w.total}
          />
        </div>

        <div>
          <ProgressBar
            value={l.save_rate}
            color="#3b82f6"
            label="Losing"
          />
          <StatRow
            label=""
            won={l.saved}
            drawn={l.drawn}
            lost={l.lost}
            total={l.total}
          />
        </div>

        <div>
          <ProgressBar
            value={e.win_rate}
            color="#eab308"
            label="Equal"
          />
          <StatRow
            label=""
            won={e.won}
            drawn={e.drawn}
            lost={e.lost}
            total={e.total}
          />
        </div>
      </div>

      <div className="mt-4 pt-3 border-t text-xs text-muted-foreground space-y-1">
        <p>
          <strong>Winning:</strong> Had &gt;200cp advantage at move 30 — converted to win?
        </p>
        <p>
          <strong>Losing:</strong> Had &gt;200cp disadvantage — managed to save/draw?
        </p>
        <p>
          <strong>Equal:</strong> Within ±200cp — outplayed opponent?
        </p>
      </div>
    </div>
  );
}
