"""Scoring and payout calculation service for Meme Mint."""

import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.caption import MMCaption

logger = logging.getLogger(__name__)


class MMScoringService:
    """Service for calculating caption quality scores and payouts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def calculate_quality_score(picks: int, shows: int) -> float:
        """Calculate quality score using the formula: (picks + 1) / (shows + 3).

        This formula:
        - Starts new captions at 0.25 (1/4) with no data
        - Rewards captions that get picked
        - Dampens the impact of small sample sizes

        Args:
            picks: Number of times caption was chosen
            shows: Number of times caption was shown

        Returns:
            Quality score between 0 and 1
        """
        return (picks + 1) / (shows + 3)

    async def update_caption_quality_score(self, caption: MMCaption) -> None:
        """Update a caption's quality score based on current shows/picks.

        Args:
            caption: Caption to update
        """
        caption.quality_score = self.calculate_quality_score(caption.picks, caption.shows)
        await self.db.flush()
        logger.debug(
            f"Updated quality score for caption {caption.caption_id}: "
            f"{caption.quality_score:.3f} ({caption.picks}/{caption.shows})"
        )

    @staticmethod
    def should_retire_caption(
        caption: MMCaption,
        min_shows_before_retirement: int,
        min_quality_score: float,
    ) -> bool:
        """Determine whether a caption should be retired based on performance.

        Args:
            caption: Caption to evaluate
            min_shows_before_retirement: Minimum shows required before retirement is considered
            min_quality_score: Quality score threshold for retirement

        Returns:
            True if the caption meets retirement criteria, otherwise False.
        """
        if caption.status != 'active':
            return False

        if caption.shows < min_shows_before_retirement:
            return False

        return caption.picks == 0 or (caption.quality_score or 0) < min_quality_score

    @staticmethod
    async def check_and_retire_caption(
        caption: MMCaption,
        config_service
    ) -> None:
        """Check if a caption meets retirement criteria and update its status."""
        min_shows = await config_service.get_config_value(
            "mm_retire_after_shows", default=5
        )
        min_quality = await config_service.get_config_value(
            "mm_min_quality_score_active", default=0.05
        )

        if MMScoringService.should_retire_caption(caption, min_shows, min_quality):
            caption.status = 'retired'
            logger.info(
                f"Retired caption {caption.caption_id} due to low performance."
            )

    @staticmethod
    def calculate_riff_split(
        total_payout: int,
        is_riff: bool
    ) -> tuple[int, int]:
        """Calculate 60/40 split for riff captions.

        For riff captions:
        - Riff author gets 60%
        - Parent author gets 40%

        For original captions:
        - Author gets 100%
        - Parent gets 0%

        Args:
            total_payout: Total payout to split
            is_riff: Whether this is a riff caption

        Returns:
            Tuple of (author_payout, parent_payout)
        """
        if not is_riff:
            return total_payout, 0

        # 60/40 split for riffs
        author_payout = int(total_payout * 0.60)
        parent_payout = int(total_payout * 0.40)

        # Handle rounding - give any remainder to the riff author
        remainder = total_payout - (author_payout + parent_payout)
        author_payout += remainder

        return author_payout, parent_payout

    @staticmethod
    def calculate_wallet_vault_split(
        gross_payout: int,
        current_lifetime_earnings: int,
        threshold: int = 100,
        post_threshold_vault_pct: float = 0.5
    ) -> tuple[int, int]:
        """Calculate wallet/vault split based on caption's lifetime earnings.

        Per MM_GAME_RULES.md Section 6:
        - First 100 MC of lifetime earnings -> 100% to wallet
        - After 100 MC threshold -> 50% to wallet, 50% to vault

        The vault is a global sink for ecosystem-wide leaderboards.
        Players' vault contributions accumulate but are not spendable.

        Args:
            gross_payout: Amount to distribute in this transaction
            current_lifetime_earnings: Caption's lifetime_earnings_gross BEFORE this payout
            threshold: Lifetime earnings threshold (default 100 MC per rules)
            post_threshold_vault_pct: Vault percentage after threshold (default 0.5 = 50%)

        Returns:
            Tuple of (wallet_amount, vault_amount)

        Example:
            Caption has earned 80 MC lifetime, receives 30 MC payout:
            - 20 MC goes to wallet (fills to 100 MC threshold)
            - 10 MC split: 5 to wallet, 5 to vault (above threshold)
            - Total: 25 MC wallet, 5 MC vault
        """
        # Calculate how much room is left before hitting the threshold
        room_to_threshold = max(0, threshold - current_lifetime_earnings)

        # Amount below threshold goes 100% to wallet
        wallet_part = min(gross_payout, room_to_threshold)

        # Amount above threshold is split according to post_threshold_vault_pct
        amount_above_threshold = max(0, gross_payout - room_to_threshold)

        if amount_above_threshold > 0:
            # Split the amount above threshold
            wallet_part += int(amount_above_threshold * (1 - post_threshold_vault_pct))
            vault_part = gross_payout - wallet_part
        else:
            vault_part = 0

        return wallet_part, vault_part

    def calculate_caption_payout(
        self,
        gross_payout: int,
        author_lifetime_earnings: int,
        parent_lifetime_earnings: int,
        is_riff: bool,
        threshold: int = 100,
        post_threshold_vault_pct: float = 0.5
    ) -> dict:
        """Calculate complete payout breakdown for a caption.

        This combines riff splitting and wallet/vault splitting to produce
        the final distribution of funds.

        Per MM_GAME_RULES.md Section 6:
        - First 100 MC of each caption's lifetime earnings -> 100% to wallet
        - After threshold -> 50% wallet, 50% vault

        Args:
            gross_payout: Total payout earned by caption
            author_lifetime_earnings: Author caption's current lifetime_earnings_gross
            parent_lifetime_earnings: Parent caption's current lifetime_earnings_gross (if riff)
            is_riff: Whether this is a riff caption
            threshold: Lifetime earnings threshold (default 100 MC)
            post_threshold_vault_pct: Vault % after threshold (default 0.5)

        Returns:
            Dictionary with payout breakdown:
            {
                'total_gross': int,
                'author_gross': int,  # Before wallet/vault split
                'parent_gross': int,  # Before wallet/vault split
                'author_wallet': int,
                'author_vault': int,
                'parent_wallet': int,
                'parent_vault': int,
            }
        """
        # First, split between author and parent (if riff)
        author_gross, parent_gross = self.calculate_riff_split(gross_payout, is_riff)

        # Then, split each portion between wallet and vault based on lifetime earnings
        author_wallet, author_vault = self.calculate_wallet_vault_split(
            author_gross,
            author_lifetime_earnings,
            threshold,
            post_threshold_vault_pct
        )

        if parent_gross > 0:
            parent_wallet, parent_vault = self.calculate_wallet_vault_split(
                parent_gross,
                parent_lifetime_earnings,
                threshold,
                post_threshold_vault_pct
            )
        else:
            parent_wallet, parent_vault = 0, 0

        logger.debug(
            f"Calculated payout: total={gross_payout}, "
            f"author={author_wallet}w+{author_vault}v, "
            f"parent={parent_wallet}w+{parent_vault}v"
        )

        return {
            'total_gross': gross_payout,
            'author_gross': author_gross,
            'parent_gross': parent_gross,
            'author_wallet': author_wallet,
            'author_vault': author_vault,
            'parent_wallet': parent_wallet,
            'parent_vault': parent_vault,
        }
