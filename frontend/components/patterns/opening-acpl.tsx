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

const VERDICT_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  "Strong — keep playing": { color: "text-green-700 dark:text-green-400", bg: "bg-green-100 dark:bg-green-950/40", label: "Strong" },
  "Solid — room to improve": { color: "text-blue-700 dark:text-blue-400", bg: "bg-blue-100 dark:bg-blue-950/40", label: "Solid" },
  "Average — needs more games": { color: "text-yellow-700 dark:text-yellow-400", bg: "bg-yellow-100 dark:bg-yellow-950/40", label: "Average" },
  "Struggling — study or consider alternatives": { color: "text-red-700 dark:text-red-400", bg: "bg-red-100 dark:bg-red-950/40", label: "Struggling" },
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
              <th className="pb-2 pr-4 font-medium">Opening</th>
              <th className="pb-2 px-3 font-medium text-center">Games</th>
              <th className="pb-2 px-3 font-medium text-center">W/L/D</th>
              <th className="pb-2 px-3 font-medium text-center">Win%</th>
              <th className="pb-2 px-3 font-medium text-center">ACPL</th>
              <th className="pb-2 px-3 font-medium text-center">Blunder%</th>
              <th className="pb-2 pl-3 font-medium text-center">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.map((o, i) => {
              const verdict = VERDICT_STYLES[o.recommendation] || { color: "", bg: "", label: o.recommendation };
              return (
                <tr key={i} className="border-b last:border-0 hover:bg-muted/50 transition-colors">
                  <td className="py-2.5 pr-4 font-medium max-w-[250px]" title={o.name}>
                    <span className="line-clamp-1">{o.name}</span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-muted-foreground">{o.games}</td>
                  <td className="py-2.5 px-3 text-center text-xs text-muted-foreground">
                    <span className="text-green-600 dark:text-green-400">{o.wins}</span>
                    {" / "}
                    <span className="text-red-500">{o.losses}</span>
                    {" / "}
                    <span>{o.draws}</span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={
                      o.win_rate >= 60 ? "text-green-600 dark:text-green-400 font-semibold" :
                      o.win_rate >= 45 ? "font-medium" :
                      "text-red-500 font-semibold"
                    }>
                      {o.win_rate}%
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={
                      o.opening_acpl > 80 ? "text-red-500 font-semibold" :
                      o.opening_acpl > 50 ? "text-yellow-600 dark:text-yellow-400 font-medium" :
                      "text-green-600 dark:text-green-400 font-medium"
                    }>
                      {o.opening_acpl}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={
                      o.blunder_rate > 8 ? "text-red-500" :
                      o.blunder_rate > 4 ? "text-yellow-600 dark:text-yellow-400" :
                      "text-muted-foreground"
                    }>
                      {o.blunder_rate}%
                    </span>
                  </td>
                  <td className="py-2.5 pl-3 text-center">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${verdict.color} ${verdict.bg}`}>
                      {verdict.label}
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
