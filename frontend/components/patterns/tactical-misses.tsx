"use client";

interface TacticalMissData {
  total_opportunities: number;
  missed: number;
  found: number;
  miss_rate: number;
  find_rate: number;
  miss_by_phase: { opening: number; middlegame: number; endgame: number };
  opportunities_by_phase: { opening: number; middlegame: number; endgame: number };
}

const FOUND_COLOR = "#22c55e";
const MISSED_COLOR = "#ef4444";

function PhaseBar({
  label,
  found,
  missed,
}: {
  label: string;
  found: number;
  missed: number;
}) {
  const total = found + missed;
  if (total === 0) return null;
  const foundPct = (found / total) * 100;
  const missedPct = (missed / total) * 100;
  const missRate = Math.round((missed / total) * 100);

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">
          {found} found · {missed} missed · {missRate}% miss rate
        </span>
      </div>
      <div className="w-full h-7 rounded-md overflow-hidden flex">
        {foundPct > 0 && (
          <div
            className="h-full flex items-center justify-center text-xs font-semibold text-white"
            style={{ width: `${foundPct}%`, backgroundColor: FOUND_COLOR, minWidth: foundPct > 5 ? "auto" : 0 }}
          >
            {foundPct >= 10 && found}
          </div>
        )}
        {missedPct > 0 && (
          <div
            className="h-full flex items-center justify-center text-xs font-semibold text-white"
            style={{ width: `${missedPct}%`, backgroundColor: MISSED_COLOR, minWidth: missedPct > 5 ? "auto" : 0 }}
          >
            {missedPct >= 10 && missed}
          </div>
        )}
      </div>
    </div>
  );
}

export function TacticalMisses({ data }: { data: TacticalMissData }) {
  if (!data || data.total_opportunities === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const phases = [
    {
      label: "Opening",
      found: data.opportunities_by_phase.opening - data.miss_by_phase.opening,
      missed: data.miss_by_phase.opening,
    },
    {
      label: "Middlegame",
      found: data.opportunities_by_phase.middlegame - data.miss_by_phase.middlegame,
      missed: data.miss_by_phase.middlegame,
    },
    {
      label: "Endgame",
      found: data.opportunities_by_phase.endgame - data.miss_by_phase.endgame,
      missed: data.miss_by_phase.endgame,
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Tactical Awareness
        </h3>
        <div className="text-right">
          <span className="text-2xl font-bold text-red-500">{data.miss_rate}%</span>
          <span className="text-xs text-muted-foreground ml-1">miss rate</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        {data.missed} of {data.total_opportunities} tactical opportunities missed
        ({data.found} found). Lower miss rate = sharper tactical vision.
      </p>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-3 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: FOUND_COLOR }} />
          <span>Found</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: MISSED_COLOR }} />
          <span>Missed</span>
        </div>
      </div>

      {/* Phase bars */}
      {phases.map((p) => (
        <PhaseBar key={p.label} label={p.label} found={p.found} missed={p.missed} />
      ))}
    </div>
  );
}
