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
        entry_cost: int,
        vault_pct: float
    ) -> tuple[int, int]:
        """Calculate wallet/vault split based on house rake percentage.

        The vault is a global sink for ecosystem-wide leaderboards.
        Players' vault contributions accumulate but are not spendable.

        Logic:
        - If gross_payout <= entry_cost (loss or break-even):
          - Everything goes to wallet (full refund of remaining value)
          - Nothing to vault
        - If gross_payout > entry_cost (profit):
          - Net profit = gross_payout - entry_cost
          - vault_amount = int(net_profit * vault_pct)
          - wallet_amount = gross_payout - vault_amount

        Args:
            gross_payout: Total payout before split
            entry_cost: Original cost to enter (for calculating net profit)
            vault_pct: Percentage of net profit to vault (e.g., 0.3 for 30%)

        Returns:
            Tuple of (wallet_amount, vault_amount)
        """
        net_profit = gross_payout - entry_cost

        if net_profit <= 0:
            # Loss or break-even: everything to wallet
            return gross_payout, 0

        # Profit: split the net profit
        vault_amount = int(net_profit * vault_pct)
        wallet_amount = gross_payout - vault_amount

        return wallet_amount, vault_amount

    def calculate_caption_payout(
        self,
        gross_payout: int,
        entry_cost: int,
        is_riff: bool,
        vault_pct: float
    ) -> dict:
        """Calculate complete payout breakdown for a caption.

        This combines riff splitting and wallet/vault splitting to produce
        the final distribution of funds.

        Args:
            gross_payout: Total payout earned by caption
            entry_cost: Original entry cost (for net profit calculation)
            is_riff: Whether this is a riff caption
            vault_pct: Vault percentage from config (e.g., 0.3)

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

        # Then, split each portion between wallet and vault
        author_wallet, author_vault = self.calculate_wallet_vault_split(
            author_gross, entry_cost, vault_pct
        )

        if parent_gross > 0:
            parent_wallet, parent_vault = self.calculate_wallet_vault_split(
                parent_gross, 0, vault_pct  # Parent has no entry cost
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
