"""Tests for the tier system."""

from src.tiers import get_tier, classify_move, TIERS, TierConfig


class TestGetTier:
    def test_none_rating_returns_beginner(self):
        tier = get_tier(None)
        assert tier.name == "beginner"

    def test_zero_rating_returns_beginner(self):
        tier = get_tier(0)
        assert tier.name == "beginner"

    def test_500_is_beginner(self):
        tier = get_tier(500)
        assert tier.name == "beginner"

    def test_799_is_beginner(self):
        tier = get_tier(799)
        assert tier.name == "beginner"

    def test_800_is_elementary(self):
        tier = get_tier(800)
        assert tier.name == "elementary"

    def test_1050_is_elementary(self):
        """Typical elementary-level rating."""
        tier = get_tier(1050)
        assert tier.name == "elementary"
        assert tier.depth == 22

    def test_1189_is_elementary(self):
        """Upper elementary-level rating."""
        tier = get_tier(1189)
        assert tier.name == "elementary"

    def test_1199_is_elementary(self):
        tier = get_tier(1199)
        assert tier.name == "elementary"

    def test_1200_is_intermediate(self):
        tier = get_tier(1200)
        assert tier.name == "intermediate"
        assert tier.depth == 24

    def test_1600_is_advanced(self):
        tier = get_tier(1600)
        assert tier.name == "advanced"
        assert tier.depth == 26

    def test_2000_is_expert(self):
        tier = get_tier(2000)
        assert tier.name == "expert"
        assert tier.depth == 28

    def test_2500_is_expert(self):
        tier = get_tier(2500)
        assert tier.name == "expert"


class TestClassifyMove:
    def test_beginner_thresholds(self):
        tier = TIERS["beginner"]
        assert classify_move(0, tier) == "excellent"
        assert classify_move(49, tier) == "excellent"
        assert classify_move(51, tier) == "good"
        assert classify_move(99, tier) == "good"
        assert classify_move(150, tier) == "inaccuracy"
        assert classify_move(250, tier) == "mistake"
        assert classify_move(501, tier) == "blunder"

    def test_elementary_thresholds(self):
        tier = TIERS["elementary"]
        assert classify_move(0, tier) == "excellent"
        assert classify_move(29, tier) == "excellent"
        assert classify_move(31, tier) == "good"
        assert classify_move(60, tier) == "inaccuracy"
        assert classify_move(150, tier) == "mistake"
        assert classify_move(301, tier) == "blunder"

    def test_advanced_thresholds_are_tighter(self):
        """Advanced players have stricter standards."""
        tier = TIERS["advanced"]
        # 80cp is a mistake for advanced, but only an inaccuracy for elementary
        assert classify_move(80, tier) == "mistake"
        assert classify_move(80, TIERS["elementary"]) == "inaccuracy"

    def test_negative_cp_loss_uses_absolute(self):
        tier = TIERS["elementary"]
        # classify_move uses abs(), so -20 → 20 → excellent
        assert classify_move(-20, tier) == "excellent"


class TestTierConfig:
    def test_all_tiers_exist(self):
        assert set(TIERS.keys()) == {"beginner", "elementary", "intermediate", "advanced", "expert"}

    def test_depth_increases_with_tier(self):
        depths = [TIERS[t].depth for t in ["beginner", "elementary", "intermediate", "advanced", "expert"]]
        assert depths == sorted(depths)

    def test_blunder_threshold_decreases_with_tier(self):
        thresholds = [TIERS[t].blunder_cp for t in ["beginner", "elementary", "intermediate", "advanced", "expert"]]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_each_tier_has_focus_areas(self):
        for name, tier in TIERS.items():
            assert len(tier.focus_areas) >= 3, f"{name} needs at least 3 focus areas"

    def test_each_tier_has_icon(self):
        for name, tier in TIERS.items():
            assert tier.icon, f"{name} needs an icon"
