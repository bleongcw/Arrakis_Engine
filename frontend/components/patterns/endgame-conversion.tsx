"use client";

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

export function EndgameConversion({ data }: { data: EndgameConversionData }) {
  if (!data || data.total_analyzed === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const w = data.winning_endgames;
  const l = data.losing_endgames;
  const e = data.equal_endgames;

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Endgame Conversion
      </h3>
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
