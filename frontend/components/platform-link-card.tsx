import { Card, CardContent } from "@/components/ui/card";

interface PlatformLinkCardProps {
  platform: "chesscom" | "lichess" | "fide";
  url: string | null;
  games?: number;
  rating?: number | null;
  subtitle?: string | null;
}

const PLATFORM_CONFIG = {
  chesscom: { icon: "\u265C", label: "CHESS.COM", borderColor: "#4a8d3f" },
  lichess: { icon: "\u265E", label: "LICHESS", borderColor: "#4a8d3f" },
  fide: { icon: "\uD83C\uDFDB", label: "FIDE", borderColor: "#b8860b" },
};

export function PlatformLinkCard({
  platform,
  url,
  games,
  rating,
  subtitle,
}: PlatformLinkCardProps) {
  const config = PLATFORM_CONFIG[platform];
  const hasData = url || rating;

  return (
    <Card
      className={`relative overflow-hidden ${
        !hasData ? "opacity-50" : ""
      }`}
      style={{ borderLeft: `3px solid ${config.borderColor}` }}
    >
      <CardContent className="p-4">
        <div className="text-2xl mb-1">{config.icon}</div>
        <div className="text-xs font-bold text-muted-foreground tracking-wider mb-2">
          {config.label}
        </div>
        {rating ? (
          <div className="text-3xl font-bold mb-1">{rating}</div>
        ) : (
          <div className="text-2xl text-muted-foreground mb-1">&mdash;</div>
        )}
        {games !== undefined && (
          <div className="text-sm text-muted-foreground">{games} games</div>
        )}
        {subtitle && (
          <div className="text-xs text-muted-foreground">{subtitle}</div>
        )}
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[#1e40af] hover:underline mt-2 inline-block"
          >
            View Profile &rarr;
          </a>
        ) : (
          <div className="text-xs text-muted-foreground mt-2">Not configured</div>
        )}
      </CardContent>
    </Card>
  );
}
