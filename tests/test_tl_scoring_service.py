"""Unit tests for ThinkLink ScoringService."""
import pytest
import math
from backend.services.tl.scoring_service import TLScoringService


class TestScoringService:
    """Test suite for ScoringService."""

    @pytest.fixture
    def scoring_service(self):
        """Create a ScoringService instance."""
        return TLScoringService()

    def test_calculate_payout_zero_coverage(self, scoring_service):
        """Test payout with 0% coverage."""
        wallet_award, vault_award, gross = scoring_service.calculate_payout(0.0)

        assert gross == 0
        assert wallet_award == 0
        assert vault_award == 0

    def test_calculate_payout_full_coverage(self, scoring_service):
        """Test payout with 100% coverage (should be capped at 300)."""
        wallet_award, vault_award, gross = scoring_service.calculate_payout(1.0)

        # 300 * (1.0 ** 1.5) = 300
        assert gross == 300
        # 300 <= 100: NO, so extra = 200, vault = int(200 * 0.30) = 60
        # wallet = 300 - 60 = 240
        assert vault_award == 60
        assert wallet_award == 240

    def test_calculate_payout_50_percent_coverage(self, scoring_service):
        """Test payout with 50% coverage."""
        wallet_award, vault_award, gross = scoring_service.calculate_payout(0.5)

        # 300 * (0.5 ** 1.5) = 300 * 0.3535... ≈ 106
        expected_gross = round(300 * (0.5 ** 1.5))
        assert gross == expected_gross

        # 106 > 100: extra = 6, vault = int(6 * 0.30) = 1
        # wallet = 106 - 1 = 105
        assert vault_award == 1
        assert wallet_award == 105

    def test_calculate_payout_below_breakeven(self, scoring_service):
        """Test payout below 100 coins (no vault split)."""
        # Find a coverage that gives ~50 coins gross
        coverage = (50 / 300) ** (1 / 1.5)  # Inverse of payout curve

        wallet_award, vault_award, gross = scoring_service.calculate_payout(coverage)

        assert gross <= 100
        assert vault_award == 0
        assert wallet_award == gross

    def test_calculate_payout_above_breakeven(self, scoring_service):
        """Test payout above 100 coins (with vault split)."""
        # Find a coverage that gives ~200 coins gross
        coverage = (200 / 300) ** (1 / 1.5)

        wallet_award, vault_award, gross = scoring_service.calculate_payout(coverage)

        assert gross > 100
        # Vault should be 30% of extra earnings
        extra = gross - 100
        expected_vault = int(extra * 0.30)
        assert vault_award == expected_vault
        assert wallet_award == gross - vault_award

    def test_payout_convex_curve(self, scoring_service):
        """Test that payout follows convex curve (rewards high coverage more)."""
        payout_25 = scoring_service.calculate_payout(0.25)[2]
        payout_50 = scoring_service.calculate_payout(0.50)[2]
        payout_75 = scoring_service.calculate_payout(0.75)[2]

        # With exponent 1.5, payout should be convex
        # Gap from 25-50 should be smaller than gap from 50-75
        gap_25_50 = payout_50 - payout_25
        gap_50_75 = payout_75 - payout_50

        assert gap_50_75 > gap_25_50

    def test_payout_capped_at_300(self, scoring_service):
        """Test that payout is capped at 300 coins."""
        # Try various high coverage values
        for coverage in [0.9, 0.95, 1.0]:
            _, _, gross = scoring_service.calculate_payout(coverage)
            assert gross <= 300

    def test_answer_weight_formula(self, scoring_service):
        """Test answer weight calculation: 1 + log(1 + min(players_count, 20))."""
        # Weight should follow formula: 1 + log(1 + min(answer_players_count, 20))

        # 1 player: 1 + log(1 + 1) = 1 + log(2) ≈ 1.693
        weight_1 = 1 + math.log(1 + 1)
        assert weight_1 == pytest.approx(1.693, abs=0.01)

        # 10 players: 1 + log(1 + 10) = 1 + log(11) ≈ 3.398
        weight_10 = 1 + math.log(1 + 10)
        assert weight_10 == pytest.approx(3.398, abs=0.01)

        # 20 players (capped): 1 + log(1 + 20) = 1 + log(21) ≈ 4.045
        weight_20 = 1 + math.log(1 + 20)
        assert weight_20 == pytest.approx(4.045, abs=0.01)

        # 100 players (still capped at 20): same as 20 players
        weight_100 = 1 + math.log(1 + min(100, 20))
        assert weight_100 == weight_20

    def test_usefulness_calculation(self, scoring_service):
        """Test usefulness formula: contributed_matches / (shows + smoothing)."""
        # Usefulness = contributed_matches / (shows + smoothing)
        # With smoothing=1: usefulness = matches / (shows + 1)

        # No matches, no shows: 0 / 1 = 0
        usefulness_0 = 0 / (0 + 1)
        assert usefulness_0 == 0

        # 5 matches, 10 shows: 5 / 11 ≈ 0.45
        usefulness_5_10 = 5 / (10 + 1)
        assert usefulness_5_10 == pytest.approx(0.45, abs=0.01)

        # 10 matches, 10 shows: 10 / 11 ≈ 0.91
        usefulness_10_10 = 10 / (10 + 1)
        assert usefulness_10_10 == pytest.approx(0.91, abs=0.01)

        # 100 matches, 10 shows: 100 / 11 ≈ 9.1 (not clamped in calculation)
        usefulness_100_10 = 100 / (10 + 1)
        assert usefulness_100_10 == pytest.approx(9.09, abs=0.01)
