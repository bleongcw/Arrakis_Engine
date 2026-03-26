const TIER_COLORS: Record<string, string> = {
  beginner: "#ef4444",
  elementary: "#f59e0b",
  intermediate: "#3b82f6",
  advanced: "#8b5cf6",
  expert: "#ec4899",
};

interface TierBadgeProps {
  tier: string;
  label: string;
  icon: string;
}

export function TierBadge({ tier, label, icon }: TierBadgeProps) {
  const color = TIER_COLORS[tier] || "#6b7280";

  return (
    <span
      className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold"
      style={{
        border: `2px solid ${color}`,
        color,
      }}
    >
      {icon} {label}
    </span>
  );
}
