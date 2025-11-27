"""Vote service for handling vote submissions and payouts in Meme Mint."""

import logging
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.caption import MMCaption
from backend.models.mm.player import MMPlayer
from backend.models.mm.vote_round import MMVoteRound
from backend.services.transaction_service import TransactionService
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.mm.scoring_service import MMScoringService
from backend.utils import lock_client

logger = logging.getLogger(__name__)

# Special UUID for system/seeded content - must match the one used in seeding
SYSTEM_PLAYER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _is_system_generated_caption(caption: MMCaption) -> bool:
    """Check if a caption is system/seeded content that should not receive payouts."""
    return caption.author_player_id == SYSTEM_PLAYER_ID or caption.author_player_id is None


class MMVoteService:
    """Service for processing votes and distributing payouts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_service = MMSystemConfigService(db)
        self.scoring_service = MMScoringService(db)

    async def submit_vote(
        self,
        round_obj: MMVoteRound,
        caption_id: UUID,
        player: MMPlayer,
        transaction_service: TransactionService
    ) -> dict:
        """Submit a vote for a caption and distribute payouts.

        This method:
        1. Validates the vote
        2. Records the chosen caption
        3. Increments caption picks counter
        4. Calculates and distributes payouts to caption authors
        5. Handles first vote bonus
        6. Applies wallet/vault split

        Args:
            round_obj: Vote round
            caption_id: ID of chosen caption
            player: Player voting
            transaction_service: Transaction service

        Returns:
            Dictionary with vote results and payout info

        Raises:
            RoundNotFoundError: Round not found or already completed
            ValueError: Invalid caption selection
        """
        # Validate inputs to prevent None player_id issues
        if not round_obj.player_id:
            logger.error(f"Round {round_obj.round_id} has no player_id")
            raise ValueError("Invalid round: missing player_id")

        if not player or not player.player_id:
            logger.error(f"Invalid player object: {player}")
            raise ValueError("Invalid player object")

        # Ensure the round belongs to the voting player
        if round_obj.player_id != player.player_id:
            logger.error(f"Player {player.player_id} trying to vote on round {round_obj.round_id} owned by {round_obj.player_id}")
            raise ValueError("Cannot vote on another player's round")

        lock_name = f"submit_vote:{round_obj.round_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Verify caption was in the round
            caption_id_str = str(caption_id)
            if caption_id_str not in round_obj.caption_ids_shown:
                raise ValueError(f"Caption {caption_id} was not shown in this round")

            # Load caption with author relationship
            stmt = select(MMCaption).where(MMCaption.caption_id == caption_id)
            result = await self.db.execute(stmt)
            caption = result.scalar_one_or_none()

            if not caption:
                raise ValueError(f"Caption {caption_id} not found")
            
            # Check if this is a system-generated caption (allow these but skip payouts)
            is_system_caption = _is_system_generated_caption(caption)
            
            # Only validate author_player_id for non-system captions
            if not is_system_caption and not caption.author_player_id:
                logger.error(f"Caption {caption_id} has no author_player_id. "
                             f"{caption.text=}, {caption.image_id=}, {caption.created_at=}, {caption.status=}")
                raise ValueError(f"Invalid caption: missing author (caption_id: {caption_id})")

            # Update round
            round_obj.chosen_caption_id = caption_id
            round_obj.result_finalized_at = datetime.now(UTC)

            # Increment caption picks and update quality score
            caption.picks += 1
            await self.scoring_service.update_caption_quality_score(caption)
            await self.scoring_service.check_and_retire_caption(
                caption, self.config_service
            )

            # Skip payouts for system-generated captions
            if not is_system_caption:
                # Get config values
                house_rake_vault_pct = await self.config_service.get_config_value(
                    "mm_house_rake_vault_pct", default=0.3)

                # Calculate and distribute payouts to caption author(s)
                payout_info = await self._distribute_caption_payouts(
                    caption,
                    round_obj.entry_cost,
                    house_rake_vault_pct,
                    transaction_service
                )

                # Check and award first vote bonus
                first_vote_bonus_awarded = await self._check_first_vote_bonus(
                    caption,
                    round_obj,
                    transaction_service
                )

                # Update round with payout info
                round_obj.payout_to_wallet = payout_info['total_wallet']
                round_obj.payout_to_vault = payout_info['total_vault']
                round_obj.first_vote_bonus_applied = first_vote_bonus_awarded
            else:
                payout_info = {
                    'total_wallet': 0,
                    'total_vault': 0
                }
                first_vote_bonus_awarded = False

            await self.db.commit()
            await self.db.refresh(player)

            logger.info(
                f"Vote submitted for round {round_obj.round_id}: "
                f"caption {caption_id}, payout {payout_info['total_wallet']}w+{payout_info['total_vault']}v"
            )

            return {
                'success': True,
                'caption_id': caption_id,
                'payout_wallet': payout_info['total_wallet'],
                'payout_vault': payout_info['total_vault'],
                'first_vote_bonus': first_vote_bonus_awarded,
                'new_wallet': player.wallet,
                'new_vault': player.vault,
            }

    async def _distribute_caption_payouts(
        self,
        caption: MMCaption,
        entry_cost: int,
        house_rake_vault_pct: float,
        transaction_service: TransactionService
    ) -> dict:
        """Distribute payouts to caption author and parent (if riff).

        For the MVP, we'll use a simple payout of the entry_cost.
        In the future, this could be based on accumulated pool, vote counts, etc.

        Args:
            caption: Chosen caption
            entry_cost: Entry cost paid by voter
            house_rake_vault_pct: Vault percentage from config
            transaction_service: Transaction service

        Returns:
            Dictionary with payout breakdown

        Raises:
            ValueError: If caption has no author or invalid author_player_id
        """
        # Validate caption has a valid author
        if not caption.author_player_id:
            logger.error(f"Caption {caption.caption_id} has no author_player_id - cannot distribute payouts")
            raise ValueError("Invalid caption: missing author_player_id")

        # Simple payout: return the entry cost to caption author(s)
        # This makes voting revenue-neutral for now
        gross_payout = entry_cost

        # Calculate split
        is_riff = caption.kind == 'riff'
        payout_breakdown = self.scoring_service.calculate_caption_payout(
            gross_payout,
            0,  # Caption author has no entry cost
            is_riff,
            house_rake_vault_pct
        )

        # Update caption earnings tracking
        caption.lifetime_earnings_gross += payout_breakdown['total_gross']
        caption.lifetime_to_wallet += payout_breakdown['author_wallet']
        caption.lifetime_to_vault += payout_breakdown['author_vault']

        # Pay caption author
        if payout_breakdown['author_wallet'] > 0:
            await transaction_service.create_transaction(
                caption.author_player_id,
                payout_breakdown['author_wallet'],
                "mm_caption_payout_wallet",
                reference_id=caption.caption_id,
                auto_commit=False,
                skip_lock=True,
                wallet_type="wallet"
            )

        if payout_breakdown['author_vault'] > 0:
            await transaction_service.create_transaction(
                caption.author_player_id,
                payout_breakdown['author_vault'],
                "mm_caption_payout_vault",
                reference_id=caption.caption_id,
                auto_commit=False,
                skip_lock=True,
                wallet_type="vault"
            )

        # Pay parent author (if riff)
        if is_riff and caption.parent_caption_id:
            parent_caption = await self.db.get(MMCaption, caption.parent_caption_id)
            if parent_caption and parent_caption.author_player_id:
                # Update parent caption earnings
                parent_caption.lifetime_earnings_gross += payout_breakdown['parent_gross']
                parent_caption.lifetime_to_wallet += payout_breakdown['parent_wallet']
                parent_caption.lifetime_to_vault += payout_breakdown['parent_vault']

                if payout_breakdown['parent_wallet'] > 0:
                    await transaction_service.create_transaction(
                        parent_caption.author_player_id,
                        payout_breakdown['parent_wallet'],
                        "mm_caption_payout_wallet",
                        reference_id=parent_caption.caption_id,
                        auto_commit=False,
                        skip_lock=True,
                        wallet_type="wallet"
                    )

                if payout_breakdown['parent_vault'] > 0:
                    await transaction_service.create_transaction(
                        parent_caption.author_player_id,
                        payout_breakdown['parent_vault'],
                        "mm_caption_payout_vault",
                        reference_id=parent_caption.caption_id,
                        auto_commit=False,
                        skip_lock=True,
                        wallet_type="vault"
                    )
            else:
                logger.warning(f"Riff caption {caption.caption_id} references parent {caption.parent_caption_id} "
                               f"but parent not found or has no author")

        return {
            'total_gross': payout_breakdown['total_gross'],
            'total_wallet': payout_breakdown['author_wallet'] + payout_breakdown['parent_wallet'],
            'total_vault': payout_breakdown['author_vault'] + payout_breakdown['parent_vault'],
            'author_wallet': payout_breakdown['author_wallet'],
            'author_vault': payout_breakdown['author_vault'],
            'parent_wallet': payout_breakdown['parent_wallet'],
            'parent_vault': payout_breakdown['parent_vault'],
        }

    async def _check_first_vote_bonus(
        self,
        caption: MMCaption,
        round_obj: MMVoteRound,
        transaction_service: TransactionService
    ) -> bool:
        """Check if this is the first vote for the caption and award bonus.

        Args:
            caption: Caption being voted on
            round_obj: Vote round
            transaction_service: Transaction service

        Returns:
            True if first vote bonus was awarded
        """
        if caption.first_vote_awarded:
            return False

        # This is the first vote! Award bonus to the voter
        bonus_amount = await self.config_service.get_config_value("mm_first_vote_bonus_amount", default=10)

        if bonus_amount > 0:
            # Use round_obj.player_id since the player who created the round is the one voting
            # Add validation to ensure player_id is not None
            if not round_obj.player_id:
                logger.error(f"Round {round_obj.round_id} has no player_id - cannot award first vote bonus")
                return False

            await transaction_service.create_transaction(
                round_obj.player_id,  # This should be the voting player's ID
                bonus_amount,
                "mm_first_vote_bonus",
                reference_id=round_obj.round_id,
                auto_commit=False,
                skip_lock=True,
                wallet_type="wallet"
            )

            caption.first_vote_awarded = True

            logger.info(
                f"First vote bonus awarded: {bonus_amount} to player {round_obj.player_id} "
                f"for caption {caption.caption_id}"
            )

            return True

        return False
