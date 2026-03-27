"use client";

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

export function CriticalPositions({ data }: { data: CriticalPositionsData }) {
  if (!data || data.total_critical === 0) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Critical Positions
      </h3>
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
        <p><strong>Under Pressure:</strong> % of critical moments (>200cp swing possible) where you found a good move</p>
        <p><strong>Capitalizing:</strong> % of opponent blunders where you took advantage</p>
      </div>
    </div>
  );
}
