"""Player tier system for adaptive analysis and coaching.

Tiers are derived from a player's current rating and drive:
- Stockfish analysis depth and time limits
- Move classification thresholds (what counts as a blunder vs mistake)
- Coaching prompt focus areas and language level
- Pattern tracking priorities
"""

from dataclasses import dataclass


# --- Tier Definitions ---

TIER_BOUNDARIES = {
    "beginner": 800,
    "elementary": 1200,
    "intermediate": 1600,
    "advanced": 2000,
    "expert": float("inf"),
}

TIER_LABELS = {
    "beginner": "Beginner",
    "elementary": "Elementary",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "expert": "Expert",
}

TIER_ICONS = {
    "beginner": "♟",
    "elementary": "♞",
    "intermediate": "♝",
    "advanced": "♜",
    "expert": "♛",
}


@dataclass
class TierConfig:
    """Configuration that adapts per tier."""

    name: str
    label: str
    icon: str
    rating_floor: int
    rating_ceiling: int

    # Stockfish settings
    depth: int
    time_limit: float  # seconds per move

    # Move classification thresholds (centipawn loss)
    excellent_cp: int
    good_cp: int
    inaccuracy_cp: int
    mistake_cp: int
    blunder_cp: int

    # Coaching focus
    focus_areas: list[str]
    language_level: str
    critical_moments_count: int

    # Description for display
    description: str


# --- Tier Configurations ---

TIERS: dict[str, TierConfig] = {
    "beginner": TierConfig(
        name="beginner",
        label="Beginner",
        icon="♟",
        rating_floor=0,
        rating_ceiling=800,
        depth=18,
        time_limit=5.0,
        excellent_cp=50,
        good_cp=100,
        inaccuracy_cp=200,
        mistake_cp=500,
        blunder_cp=500,
        focus_areas=[
            "Hanging pieces — check if your pieces are safe before moving",
            "Basic checkmate patterns (back rank, queen + rook)",
            "One-move tactics — look for pieces you can capture for free",
            "Piece development — get all your pieces out in the opening",
        ],
        language_level="Simple, concrete, story-like. Short sentences. No abstract theory.",
        critical_moments_count=3,
        description="Learning the pieces and basic tactics",
    ),
    "elementary": TierConfig(
        name="elementary",
        label="Elementary",
        icon="♞",
        rating_floor=800,
        rating_ceiling=1200,
        depth=22,
        time_limit=10.0,
        excellent_cp=30,
        good_cp=50,
        inaccuracy_cp=100,
        mistake_cp=300,
        blunder_cp=300,
        focus_areas=[
            "Tactical patterns — pins, forks, skewers, discovered attacks",
            "Piece activity — are your pieces on good squares?",
            "King safety — keep your king castled and protected",
            "Basic opening principles — control the center, develop, castle",
            "Simple endgames — king + pawn, rook endgames",
        ],
        language_level="Age-appropriate, concrete with some chess terms introduced. "
        "Name tactical patterns when they appear.",
        critical_moments_count=5,
        description="Building tactical vision and pattern recognition",
    ),
    "intermediate": TierConfig(
        name="intermediate",
        label="Intermediate",
        icon="♝",
        rating_floor=1200,
        rating_ceiling=1600,
        depth=24,
        time_limit=12.0,
        excellent_cp=20,
        good_cp=40,
        inaccuracy_cp=70,
        mistake_cp=200,
        blunder_cp=200,
        focus_areas=[
            "Pawn structure — isolated, doubled, backward pawns and how to exploit them",
            "Piece coordination — making your pieces work together",
            "Positional play — good vs bad bishops, outposts, open files",
            "Opening repertoire — building consistent openings for both colors",
            "Calculation — seeing 3-4 moves ahead accurately",
            "Endgame technique — opposition, pawn races, rook activity",
        ],
        language_level="Full chess vocabulary. Can discuss positional concepts. "
        "Reference specific openings by name.",
        critical_moments_count=7,
        description="Developing positional understanding and calculation",
    ),
    "advanced": TierConfig(
        name="advanced",
        label="Advanced",
        icon="♜",
        rating_floor=1600,
        rating_ceiling=2000,
        depth=26,
        time_limit=15.0,
        excellent_cp=15,
        good_cp=30,
        inaccuracy_cp=60,
        mistake_cp=150,
        blunder_cp=150,
        focus_areas=[
            "Prophylaxis — preventing opponent's plans before executing yours",
            "Pawn breaks and dynamic play",
            "Strategic planning — forming and executing multi-move plans",
            "Opening preparation — knowing theory and finding novelties",
            "Complex endgames — rook + pawn, bishop vs knight",
            "Time management — when to think deeply vs play quickly",
        ],
        language_level="Technical and strategic. Discuss plans, prophylaxis, "
        "structural advantages. Reference model games.",
        critical_moments_count=8,
        description="Mastering strategy, planning, and deep calculation",
    ),
    "expert": TierConfig(
        name="expert",
        label="Expert",
        icon="♛",
        rating_floor=2000,
        rating_ceiling=9999,
        depth=28,
        time_limit=20.0,
        excellent_cp=10,
        good_cp=20,
        inaccuracy_cp=40,
        mistake_cp=100,
        blunder_cp=100,
        focus_areas=[
            "Opening novelties and preparation depth",
            "Subtle positional inaccuracies",
            "Transition from middlegame to endgame",
            "Psychological aspects — when opponents deviate from theory",
            "Time trouble decision-making",
            "Competitive preparation against specific opponents",
        ],
        language_level="Expert-level analysis. Assume deep chess knowledge. "
        "Reference concrete variations and theoretical lines.",
        critical_moments_count=10,
        description="Refining at the highest level",
    ),
}


def get_tier(rating: int | None) -> TierConfig:
    """Get the tier configuration for a given rating.

    Args:
        rating: Player's current rating. If None, defaults to beginner.

    Returns:
        TierConfig for the appropriate tier.
    """
    if rating is None:
        return TIERS["beginner"]

    if rating < 800:
        return TIERS["beginner"]
    elif rating < 1200:
        return TIERS["elementary"]
    elif rating < 1600:
        return TIERS["intermediate"]
    elif rating < 2000:
        return TIERS["advanced"]
    else:
        return TIERS["expert"]


def get_player_tier(conn, player_id: int) -> TierConfig:
    """Get the tier for a player based on their latest game rating.

    Falls back to the stored rating in the players table, then to beginner.
    """
    # Try latest game rating first
    row = conn.execute(
        """SELECT player_rating FROM games
        WHERE player_id = ? AND player_rating IS NOT NULL
        ORDER BY date_played DESC LIMIT 1""",
        (player_id,),
    ).fetchone()

    if row and row["player_rating"]:
        return get_tier(row["player_rating"])

    # Fall back to stored rating
    player = conn.execute(
        "SELECT rating FROM players WHERE id = ?", (player_id,)
    ).fetchone()

    if player and player["rating"]:
        return get_tier(player["rating"])

    return TIERS["beginner"]


def classify_move(cp_loss: float, tier: TierConfig) -> str:
    """Classify a move based on centipawn loss and tier thresholds.

    Args:
        cp_loss: Absolute centipawn loss (positive = worse move).
        tier: The TierConfig determining thresholds.

    Returns:
        One of: 'excellent', 'good', 'inaccuracy', 'mistake', 'blunder'
    """
    cp_loss = abs(cp_loss)

    if cp_loss < tier.excellent_cp:
        return "excellent"
    elif cp_loss < tier.good_cp:
        return "good"
    elif cp_loss < tier.inaccuracy_cp:
        return "inaccuracy"
    elif cp_loss < tier.mistake_cp:
        return "mistake"
    else:
        return "blunder"
