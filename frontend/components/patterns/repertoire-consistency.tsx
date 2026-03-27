"use client";

interface RepertoireData {
  white: ColorRepertoire;
  black: ColorRepertoire;
  total_unique: number;
}

interface ColorRepertoire {
  unique_openings: number;
  top_3: Array<{ name: string; games: number; pct: number }>;
  top_3_pct: number;
  consistency_score: number;
  rating: string;
}

const RATING_COLORS: Record<string, string> = {
  "Very focused": "text-green-600 dark:text-green-400",
  "Reasonably consistent": "text-blue-600 dark:text-blue-400",
  "Scattered": "text-yellow-600 dark:text-yellow-400",
  "No clear repertoire": "text-red-500",
  "No games": "text-muted-foreground",
};

function ColorSection({ label, icon, data }: { label: string; icon: string; data: ColorRepertoire }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{icon} {label}</span>
        <span className={`text-xs font-semibold ${RATING_COLORS[data.rating] || ""}`}>
          {data.rating}
        </span>
      </div>

      <div className="flex items-center gap-3 mb-2">
        <div className="flex-1">
          <div className="w-full h-2.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${data.top_3_pct}%` }}
            />
          </div>
        </div>
        <span className="text-xs text-muted-foreground w-16 text-right">
          Top 3: {data.top_3_pct}%
        </span>
      </div>

      <div className="space-y-1">
        {data.top_3.map((o, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="truncate max-w-[180px]" title={o.name}>
              {i + 1}. {o.name}
            </span>
            <span className="text-muted-foreground ml-2 whitespace-nowrap">
              {o.games} games ({o.pct}%)
            </span>
          </div>
        ))}
      </div>

      <div className="text-xs text-muted-foreground mt-1">
        {data.unique_openings} unique openings played
      </div>
    </div>
  );
}

export function RepertoireConsistency({ data }: { data: RepertoireData }) {
  if (!data) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Repertoire Consistency
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        Focused repertoire = faster improvement. Shows how concentrated your opening choices are.
      </p>

      <div className="space-y-5">
        <ColorSection label="As White" icon="♔" data={data.white} />
        <div className="border-t" />
        <ColorSection label="As Black" icon="♚" data={data.black} />
      </div>

      <div className="mt-4 pt-3 border-t text-xs text-muted-foreground">
        <p>{data.total_unique} total unique openings across both colors.</p>
        <p className="mt-1">
          <strong>Tip:</strong> At the elementary/intermediate level, focusing on 2-3 openings per color
          builds deeper understanding faster than playing many different systems.
        </p>
      </div>
    </div>
  );
}
