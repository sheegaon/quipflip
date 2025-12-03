"""Vote service for handling vote submissions and payouts in Meme Mint."""

import logging
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.caption import MMCaption
from backend.models.mm.caption_seen import MMCaptionSeen
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
            logger.error(f"Player {player.player_id} trying to vote on round {round_obj.round_id} owned by "
            f"{round_obj.player_id}")
            raise ValueError("Cannot vote on another player's round")

        lock_name = f"submit_vote:{round_obj.round_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Verify caption was in the round
            caption_id_str = str(caption_id)
            if caption_id_str not in round_obj.caption_ids_shown:
                raise ValueError(f"Caption {caption_id} was not shown in this round")

            # Load all captions shown in the round (including chosen caption)
            caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]
            stmt = select(MMCaption).where(MMCaption.caption_id.in_(caption_ids))
            result = await self.db.execute(stmt)
            captions = result.scalars().all()

            captions_by_id = {cap.caption_id: cap for cap in captions}
            caption = captions_by_id.get(caption_id)

            all_captions_are_system = all(
                _is_system_generated_caption(cap) for cap in captions_by_id.values()
            )

            if not caption:
                raise ValueError(f"Caption {caption_id} not found")

            if len(captions_by_id) != len(caption_ids):
                missing_ids = set(caption_ids) - set(captions_by_id.keys())
                logger.warning(f"Some captions from round {round_obj.round_id} were not found: {missing_ids}")

            # Check if this is a system-generated caption (allow these but skip payouts)
            is_system_caption = _is_system_generated_caption(caption)
            
            # Only validate author_player_id for non-system captions
            if not is_system_caption and not caption.author_player_id:
                logger.error(f"Caption {caption_id} has no author_player_id. "
                             f"{caption.text=}, {caption.image_id=}, {caption.created_at=}, {caption.status=}")
                raise ValueError(f"Invalid caption: missing author (caption_id: {caption_id})")

            # Apply local crowd favorite bonus before mutating vote counts
            pre_vote_counts = {cap_id: cap.picks for cap_id, cap in captions_by_id.items()}
            local_crowd_favorite_awarded = await self._maybe_apply_local_crowd_favorite_bonus(
                round_obj,
                caption_id,
                pre_vote_counts,
                transaction_service
            )

            # Update round
            round_obj.chosen_caption_id = caption_id
            round_obj.result_finalized_at = datetime.now(UTC)

            # Per MM_GAME_RULES.md Section 4.4: Increment shows for all 5 captions
            # and mark them as seen AFTER vote (not during round start)
            await self._increment_caption_shows_and_mark_seen(round_obj, player.player_id)

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
                    transaction_service,
                    voter_player_id=player.player_id  # Pass voter ID for Circle-mate checking
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

            # Refund entry if the round only showed system-generated captions
            if all_captions_are_system:
                await transaction_service.create_transaction(
                    player.player_id,
                    round_obj.entry_cost,
                    "mm_round_entry_refund",
                    reference_id=round_obj.round_id,
                    auto_commit=False,
                )
                logger.info(
                    "Refunded entry cost for all-system caption round",
                    extra={"round_id": round_obj.round_id, "player_id": player.player_id}
                )

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
                'payout_info': payout_info,
                'first_vote_bonus': first_vote_bonus_awarded,
                'local_crowd_favorite_bonus': local_crowd_favorite_awarded,
                'new_wallet': player.wallet,
                'new_vault': player.vault,
            }

    async def _distribute_caption_payouts(
        self,
        caption: MMCaption,
        entry_cost: int,
        house_rake_vault_pct: float,
        transaction_service: TransactionService,
        voter_player_id: UUID = None
    ) -> dict:
        """Distribute payouts to caption author and parent (if riff).

        Per MM_GAME_RULES.md Section 4.5-4.6:
        - Base payout = entry_cost (from voter)
        - Writer bonus = entry_cost * WRITER_BONUS_MULTIPLIER (minted by system)
        - Total gross payout = entry_cost * (1 + WRITER_BONUS_MULTIPLIER)

        Per MM_CIRCLES.md Section 6:
        - System bonus is suppressed when voter is a Circle-mate of the author
        - Base payout is always given

        Args:
            caption: Chosen caption
            entry_cost: Entry cost paid by voter
            house_rake_vault_pct: Vault percentage from config
            transaction_service: Transaction service
            voter_player_id: ID of the voting player (for Circle-mate bonus suppression)

        Returns:
            Dictionary with payout breakdown

        Raises:
            ValueError: If caption has no author or invalid author_player_id
        """
        from backend.services.mm.circle_service import MMCircleService

        # Validate caption has a valid author
        if not caption.author_player_id:
            logger.error(f"Caption {caption.caption_id} has no author_player_id - cannot distribute payouts")
            raise ValueError("Invalid caption: missing author_player_id")

        # Get Circle-mates of voter for bonus suppression
        circle_mates = set()
        if voter_player_id:
            circle_mates = await MMCircleService.get_circle_mates(self.db, voter_player_id)

        # Get writer bonus multiplier from config (default 3 per game rules)
        writer_bonus_multiplier = await self.config_service.get_config_value(
            "mm_writer_bonus_multiplier", default=3
        )

        # Check if caption author is a Circle-mate of voter
        author_is_circle_mate = caption.author_player_id in circle_mates

        # Calculate base payout (always given) and writer bonus (suppressed for Circle-mates)
        # Example: entry_cost=5, multiplier=3
        # - For non-Circle-mate: gross = 5 + (5*3) = 20 MC
        # - For Circle-mate: gross = 5 + 0 = 5 MC (bonus suppressed)
        base_payout = entry_cost
        author_writer_bonus = 0 if author_is_circle_mate else (entry_cost * writer_bonus_multiplier)

        if author_is_circle_mate:
            logger.info(
                f"System bonus suppressed for caption {caption.caption_id} author "
                f"{caption.author_player_id} (Circle-mate of voter {voter_player_id})"
            )

        # For riffs, check parent author separately
        parent_writer_bonus = 0
        parent_caption = None
        is_riff = caption.kind == 'riff'

        if is_riff and caption.parent_caption_id:
            parent_caption = await self.db.get(MMCaption, caption.parent_caption_id)
            if parent_caption and parent_caption.author_player_id:
                parent_is_circle_mate = parent_caption.author_player_id in circle_mates
                parent_writer_bonus = 0 if parent_is_circle_mate else (entry_cost * writer_bonus_multiplier)

                if parent_is_circle_mate:
                    logger.info(
                        f"System bonus suppressed for parent caption {parent_caption.caption_id} author "
                        f"{parent_caption.author_player_id} (Circle-mate of voter {voter_player_id})"
                    )

        # Calculate payouts with Circle-aware bonuses
        if is_riff:
            # For riffs, base payout is applied to both the riff author and the parent separately
            author_gross = base_payout + author_writer_bonus
            parent_gross = (base_payout + parent_writer_bonus) if parent_caption else 0
            total_gross = author_gross + parent_gross

            # Apply wallet/vault split independently for author and parent
            author_wallet, author_vault = self.scoring_service.calculate_wallet_vault_split(
                author_gross,
                caption.lifetime_earnings_gross
            )

            parent_wallet, parent_vault = (0, 0)
            if parent_caption:
                parent_wallet, parent_vault = self.scoring_service.calculate_wallet_vault_split(
                    parent_gross,
                    parent_caption.lifetime_earnings_gross
                )

            payout_breakdown = {
                'total_gross': total_gross,
                'author_gross': author_gross,
                'parent_gross': parent_gross,
                'author_wallet': author_wallet,
                'author_vault': author_vault,
                'parent_wallet': parent_wallet,
                'parent_vault': parent_vault,
                'total_wallet': author_wallet + parent_wallet,
                'total_vault': author_vault + parent_vault,
            }
        else:
            # Originals retain existing logic (base + bonus, split via helper)
            gross_payout = base_payout + author_writer_bonus

            payout_breakdown = self.scoring_service.calculate_caption_payout(
                gross_payout,
                caption.lifetime_earnings_gross,
                0,
                is_riff
            )

            payout_breakdown['total_wallet'] = payout_breakdown['author_wallet']
            payout_breakdown['total_vault'] = payout_breakdown['author_vault']

        # Update caption earnings tracking
        caption.lifetime_earnings_gross += payout_breakdown['author_gross']
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

        # Pay parent author (if riff) - reuse parent_caption loaded earlier
        if is_riff and parent_caption and parent_caption.author_player_id:
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
        elif is_riff and caption.parent_caption_id:
            logger.warning(f"Riff caption {caption.caption_id} references parent {caption.parent_caption_id} "
                           f"but parent not found or has no author")

        return {
            'total_gross': payout_breakdown['total_gross'],
            'total_wallet': payout_breakdown['author_wallet'] + payout_breakdown['parent_wallet'],
            'total_vault': payout_breakdown['author_vault'] + payout_breakdown['parent_vault'],
            'author_gross': payout_breakdown['author_gross'],
            'author_wallet': payout_breakdown['author_wallet'],
            'author_vault': payout_breakdown['author_vault'],
            'parent_gross': payout_breakdown['parent_gross'],
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
        bonus_amount = await self.config_service.get_config_value("mm_first_vote_bonus_amount", default=2)

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

    async def _increment_caption_shows_and_mark_seen(
        self,
        round_obj: MMVoteRound,
        player_id: UUID
    ) -> None:
        """Increment shows for all captions in round and mark as seen.

        Per MM_GAME_RULES.md Section 4.4, this happens AFTER vote submission,
        not during round start.

        Args:
            round_obj: The vote round
            player_id: Player who voted
        """
        # Load all captions shown in this round
        caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]
        stmt = select(MMCaption).where(MMCaption.caption_id.in_(caption_ids))
        result = await self.db.execute(stmt)
        captions = list(result.scalars().all())

        # Increment shows counter and update quality scores
        for caption in captions:
            caption.shows += 1
            caption.quality_score = self.scoring_service.calculate_quality_score(
                caption.picks, caption.shows
            )
            logger.debug(
                f"Updated shows for caption {caption.caption_id}: "
                f"{caption.quality_score:.3f} ({caption.picks}/{caption.shows})"
            )

        # Mark all captions as seen by this player, avoiding duplicate inserts
        existing_seen_stmt = select(MMCaptionSeen.caption_id).where(
            MMCaptionSeen.player_id == player_id,
            MMCaptionSeen.caption_id.in_(caption_ids),
        )
        existing_seen = await self.db.execute(existing_seen_stmt)
        already_seen_ids = set(existing_seen.scalars().all())

        for caption in captions:
            if caption.caption_id in already_seen_ids:
                continue

            seen_record = MMCaptionSeen(
                player_id=player_id,
                caption_id=caption.caption_id,
                image_id=round_obj.image_id,
                first_seen_at=datetime.now(UTC),
            )
            self.db.add(seen_record)

        await self.db.flush()

    async def _maybe_apply_local_crowd_favorite_bonus(
        self,
        round_obj: MMVoteRound,
        chosen_caption_id: UUID,
        pre_vote_counts: dict[UUID, int],
        transaction_service: TransactionService
    ) -> bool:
        """Award the local crowd favorite bonus when applicable.

        The bonus triggers if at least three captions have been picked before and
        there is a unique leader in global pick count that matches the player's
        selection. Counts are evaluated before this vote's mutations.
        """
        if sum(1 for count in pre_vote_counts.values() if count > 0) < 3:
            return False

        max_count = max(pre_vote_counts.values(), default=0)

        leaders = [cid for cid, count in pre_vote_counts.items() if count == max_count]
        if len(leaders) != 1:
            return False

        if leaders[0] != chosen_caption_id:
            return False

        wallet_amount = await self.config_service.get_config_value(
            "mm_lcf_bonus_wallet",
            default=2,
        )
        vault_amount = await self.config_service.get_config_value(
            "mm_lcf_bonus_vault",
            default=1,
        )

        await transaction_service.create_transaction(
            round_obj.player_id,
            wallet_amount,
            "mm_local_crowd_favorite_bonus",
            reference_id=round_obj.round_id,
            auto_commit=False,
            skip_lock=True,
            wallet_type="wallet"
        )

        await transaction_service.create_transaction(
            round_obj.player_id,
            vault_amount,
            "mm_local_crowd_favorite_bonus",
            reference_id=round_obj.round_id,
            auto_commit=False,
            skip_lock=True,
            wallet_type="vault"
        )

        logger.info(
            f"Local crowd favorite bonus awarded for round {round_obj.round_id}: "
            f"{wallet_amount}w+{vault_amount}v to player {round_obj.player_id}"
        )

        return True
