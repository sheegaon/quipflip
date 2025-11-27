"""Game service for managing Meme Mint rounds - image/caption selection."""

import logging
import random
from datetime import datetime, UTC, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import or_

from backend.models.mm.image import MMImage
from backend.models.mm.caption import MMCaption
from backend.models.mm.caption_seen import MMCaptionSeen
from backend.models.mm.player import MMPlayer
from backend.models.mm.vote_round import MMVoteRound
from backend.services.transaction_service import TransactionService
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.mm.scoring_service import MMScoringService
from backend.config import get_settings
from backend.utils import lock_client, ensure_utc
from backend.utils.exceptions import (
    RoundNotFoundError,
    RoundExpiredError,
    NoContentAvailableError,
    InsufficientBalanceError,
)

logger = logging.getLogger(__name__)


class MMGameService:
    """Service for managing Meme Mint game rounds."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.config_service = MMSystemConfigService(db)
        self.scoring_service = MMScoringService(db)
        self._has_seeded_placeholder = False

    async def _seed_placeholder_content(self) -> None:
        """Seed Meme Mint data for non-production environments when empty."""
        if self.settings.environment == "production":
            return

        # Avoid repeated imports/seed calls within the same request
        if self._has_seeded_placeholder:
            return

        from backend.data.seed_mm_data import seed_data as seed_mm_data

        await seed_mm_data(self.db)
        self._has_seeded_placeholder = True

    async def start_vote_round(
        self,
        player: MMPlayer,
        transaction_service: TransactionService
    ) -> MMVoteRound:
        """Start a vote round for a player.

        Selects an image with at least CAPTIONS_PER_ROUND unseen captions,
        then selects captions using weighted random by quality_score.

        Args:
            player: Player starting the round
            transaction_service: Transaction service for payment

        Returns:
            Created vote round

        Raises:
            NoContentAvailableError: No eligible images/captions available
            InsufficientBalanceError: Player cannot afford entry cost
        """
        lock_name = f"start_vote_round:{player.player_id}"
        with lock_client.lock(lock_name, timeout=self.settings.round_lock_timeout_seconds):
            # Get config values
            entry_cost = await self.config_service.get_config_value("mm_round_entry_cost", default=5)
            captions_per_round = await self.config_service.get_config_value("mm_captions_per_round", default=5)
            round_duration_seconds = self.settings.vote_round_seconds

            # Check player balance
            if player.wallet < entry_cost:
                raise InsufficientBalanceError(
                    f"Insufficient balance. Need {entry_cost}, have {player.wallet}"
                )

            # Select image with enough unseen captions; if empty in non-prod, seed placeholders and retry once
            image = await self._select_image_for_vote(player.player_id, captions_per_round)
            if not image:
                await self._seed_placeholder_content()
                image = await self._select_image_for_vote(player.player_id, captions_per_round)

            if not image:
                raise NoContentAvailableError("No images available with enough unseen captions")

            # Select captions using weighted random. If insufficient, seed and retry once.
            try:
                captions = await self._select_captions_for_round(
                    image.image_id,
                    player.player_id,
                    captions_per_round
                )
            except NoContentAvailableError:
                await self._seed_placeholder_content()
                # Re-select image in case new content was added
                image = await self._select_image_for_vote(player.player_id, captions_per_round) or image
                captions = await self._select_captions_for_round(
                    image.image_id,
                    player.player_id,
                    captions_per_round
                )

            # Charge entry cost
            await transaction_service.create_transaction(
                player.player_id,
                -entry_cost,
                "mm_round_entry",
                auto_commit=False,
                skip_lock=True,
            )

            # Create round
            round_obj = MMVoteRound(
                round_id=uuid4(),
                player_id=player.player_id,
                image_id=image.image_id,
                # Store UUIDs as strings to satisfy JSON serialization
                caption_ids_shown=[str(c.caption_id) for c in captions],
                entry_cost=entry_cost,
                created_at=datetime.now(UTC),
            )

            self.db.add(round_obj)
            await self.db.flush([round_obj])

            # NOTE: shows and seen_captions are now updated AFTER vote submission
            # (moved to vote_service.submit_vote() per MM_GAME_RULES.md Section 4.4)

            await self.db.commit()

            logger.info(
                f"Started vote round {round_obj.round_id} for player {player.player_id}: "
                f"image {image.image_id}, {len(captions)} captions"
            )

            return round_obj

    async def _select_image_for_vote(
        self,
        player_id: UUID,
        captions_per_round: int
    ) -> Optional[MMImage]:
        """Select an image that has at least captions_per_round unseen captions.

        Args:
            player_id: Player ID
            captions_per_round: Minimum number of captions needed

        Returns:
            Selected image or None if no eligible images
        """
        # Subquery: count unseen active captions per image
        unseen_captions_subq = (
            select(
                MMCaption.image_id,
                func.count(MMCaption.caption_id).label('unseen_count')
            )
            .outerjoin(
                MMCaptionSeen,
                and_(
                    MMCaptionSeen.caption_id == MMCaption.caption_id,
                    MMCaptionSeen.player_id == player_id
                )
            )
            .where(
                MMCaption.status == 'active',
                # Allow system/anonymous captions (NULL author) while excluding the player's own
                or_(MMCaption.author_player_id.is_(None), MMCaption.author_player_id != player_id),
                MMCaptionSeen.player_id.is_(None)  # Not seen
            )
            .group_by(MMCaption.image_id)
            .having(func.count(MMCaption.caption_id) >= captions_per_round)
            .subquery()
        )

        # Select random image from eligible images
        stmt = (
            select(MMImage)
            .join(unseen_captions_subq, unseen_captions_subq.c.image_id == MMImage.image_id)
            .where(MMImage.status == 'active')
            .order_by(func.random())
            .limit(10)  # Get 10 candidates for better randomness
        )

        result = await self.db.execute(stmt)
        images = result.scalars().all()

        if not images:
            return None

        # Randomly select one from candidates (more efficient than ORDER BY random())
        return random.choice(images)

    async def _select_captions_for_round(
        self,
        image_id: UUID,
        player_id: UUID,
        count: int
    ) -> list[MMCaption]:
        """Select captions using weighted random by quality_score.

        Args:
            image_id: Image to select captions for
            player_id: Player ID (to exclude seen captions)
            count: Number of captions to select

        Returns:
            List of selected captions
        """
        # Get candidate captions
        stmt = (
            select(MMCaption)
            .outerjoin(
                MMCaptionSeen,
                and_(
                    MMCaptionSeen.caption_id == MMCaption.caption_id,
                    MMCaptionSeen.player_id == player_id
                )
            )
            .where(
                MMCaption.image_id == image_id,
                MMCaption.status == 'active',
                # Allow captions without an author while excluding the player's own
                or_(MMCaption.author_player_id.is_(None), MMCaption.author_player_id != player_id),
                MMCaptionSeen.player_id.is_(None)
            )
        )

        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        if len(candidates) < count:
            raise NoContentAvailableError(
                f"Not enough unseen captions for image {image_id}. "
                f"Need {count}, have {len(candidates)}"
            )

        # Weighted random selection by quality_score, without replacement
        weights = [caption.quality_score or 0 for caption in candidates]
        selected: list[MMCaption] = []
        available = list(candidates)

        for _ in range(count):
            if not available:
                break

            total_weight = sum(weights)
            if total_weight <= 0:
                idx = random.randrange(len(available))
            else:
                pick = random.uniform(0, total_weight)
                cumulative = 0.0
                idx = 0
                for i, w in enumerate(weights):
                    cumulative += w
                    if pick <= cumulative:
                        idx = i
                        break

            selected.append(available.pop(idx))
            weights.pop(idx)

        logger.debug(
            f"Selected {count} captions for image {image_id} using weighted random. "
            f"Quality scores: {[f'{c.quality_score:.3f}' for c in selected]}"
        )

        return selected

    async def _mark_captions_as_seen(
        self,
        player_id: UUID,
        image_id: UUID,
        captions: list[MMCaption]
    ) -> None:
        """Mark captions as seen by player.

        Args:
            player_id: Player ID
            image_id: Image ID
            captions: List of captions to mark as seen
        """
        for caption in captions:
            seen_record = MMCaptionSeen(
                player_id=player_id,
                caption_id=caption.caption_id,
                image_id=image_id,
                first_seen_at=datetime.now(UTC),
            )
            self.db.add(seen_record)

        await self.db.flush()

    async def _increment_caption_shows(self, captions: list[MMCaption]) -> None:
        """Increment shows counter for captions and update quality scores.

        Args:
            captions: List of captions to increment
        """
        for caption in captions:
            caption.shows += 1
            # Update quality score but don't flush yet - we'll batch flush all changes
            caption.quality_score = self.scoring_service.calculate_quality_score(
                caption.picks, caption.shows
            )

            await self.scoring_service.check_and_retire_caption(
                caption, self.config_service
            )
            logger.debug(
                f"Updated quality score for caption {caption.caption_id}: "
                f"{caption.quality_score:.3f} ({caption.picks}/{caption.shows})"
            )

        # Single batch flush for all updated captions
        await self.db.flush()

    async def get_round(self, round_id: UUID, player_id: UUID) -> Optional[MMVoteRound]:
        """Get a round by ID, ensuring it belongs to the player.

        Args:
            round_id: Round ID
            player_id: Player ID

        Returns:
            Round or None if not found
        """
        stmt = select(MMVoteRound).where(
            MMVoteRound.round_id == round_id,
            MMVoteRound.player_id == player_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_round_with_relations(self, round_id: UUID) -> Optional[MMVoteRound]:
        """Get a round with all its relationships loaded.

        Args:
            round_id: Round ID

        Returns:
            Round with relationships or None
        """
        stmt = (
            select(MMVoteRound)
            .where(MMVoteRound.round_id == round_id)
        )
        result = await self.db.execute(stmt)
        round_obj = result.scalar_one_or_none()

        if round_obj:
            # Load relationships
            await self.db.refresh(round_obj, ['image', 'player', 'chosen_caption'])

        return round_obj

    def check_round_expired(self, round_obj: MMVoteRound) -> bool:
        """Check if a round has expired past grace period.

        Args:
            round_obj: Round to check

        Returns:
            True if expired past grace period
        """
        expires_at = ensure_utc(round_obj.created_at) + timedelta(
            seconds=self.settings.vote_round_seconds
        )
        grace_cutoff = expires_at + timedelta(
            seconds=self.settings.grace_period_seconds
        )
        return datetime.now(UTC) > grace_cutoff
