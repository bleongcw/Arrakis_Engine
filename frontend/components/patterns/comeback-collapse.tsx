"use client";

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

export function ComebackCollapse({ data }: { data: ComebackCollapseData }) {
  if (!data) {
    return <p className="text-sm text-muted-foreground">No data available.</p>;
  }

  const cb = data.comebacks;
  const cl = data.collapses;

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Resilience & Composure
      </h3>
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
