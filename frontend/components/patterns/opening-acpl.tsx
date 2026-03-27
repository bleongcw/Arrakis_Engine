"use client";

interface OpeningACPLEntry {
  name: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  opening_acpl: number;
  blunder_rate: number;
  recommendation: string;
}

const RECOMMENDATION_COLORS: Record<string, string> = {
  "Strong — keep playing": "text-green-600 dark:text-green-400",
  "Solid — room to improve": "text-blue-600 dark:text-blue-400",
  "Average — needs more games": "text-yellow-600 dark:text-yellow-400",
  "Struggling — study or consider alternatives": "text-red-500",
};

export function OpeningACPL({ data }: { data: OpeningACPLEntry[] }) {
  if (!data || data.length === 0) {
    return <p className="text-sm text-muted-foreground">No data available. Need 3+ games per opening.</p>;
  }

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Opening Quality Analysis
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        ACPL during opening phase (moves 1-15) per opening. Higher ACPL = more errors in that opening.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground uppercase tracking-wider">
              <th className="pb-2 font-medium">Opening</th>
              <th className="pb-2 font-medium text-right">Games</th>
              <th className="pb-2 font-medium text-right">Win%</th>
              <th className="pb-2 font-medium text-right">ACPL</th>
              <th className="pb-2 font-medium text-right">Blunder%</th>
              <th className="pb-2 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.map((o, i) => (
              <tr key={i} className="border-b last:border-0">
                <td className="py-2 font-medium max-w-[200px] truncate" title={o.name}>
                  {o.name}
                </td>
                <td className="py-2 text-right text-muted-foreground">{o.games}</td>
                <td className="py-2 text-right">
                  <span className={o.win_rate >= 50 ? "text-green-600 dark:text-green-400" : o.win_rate >= 40 ? "" : "text-red-500"}>
                    {o.win_rate}%
                  </span>
                </td>
                <td className="py-2 text-right">
                  <span className={o.opening_acpl > 80 ? "text-red-500 font-medium" : o.opening_acpl > 50 ? "text-yellow-600" : "text-green-600 dark:text-green-400"}>
                    {o.opening_acpl}
                  </span>
                </td>
                <td className="py-2 text-right text-muted-foreground">{o.blunder_rate}%</td>
                <td className="py-2">
                  <span className={`text-xs ${RECOMMENDATION_COLORS[o.recommendation] || ""}`}>
                    {o.recommendation}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
