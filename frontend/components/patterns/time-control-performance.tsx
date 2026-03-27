"use client";

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

export function TimeControlPerformance({ data }: { data: TimeControlData }) {
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
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Time Control Performance
      </h3>
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
