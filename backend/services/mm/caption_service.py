"""Caption service for handling caption submissions in Meme Mint."""

import logging
from datetime import datetime, UTC
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.caption import MMCaption
from backend.models.mm.caption_submission import MMCaptionSubmission
from backend.models.mm.image import MMImage
from backend.models.mm.player import MMPlayer
from backend.services.transaction_service import TransactionService
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.mm.daily_state_service import MMPlayerDailyStateService
from backend.services.mm.scoring_service import MMScoringService
from backend.services.phrase_validator import get_phrase_validator
from backend.utils import lock_client
from backend.utils.exceptions import InsufficientBalanceError

logger = logging.getLogger(__name__)


class MMCaptionService:
    """Service for managing caption submissions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_service = MMSystemConfigService(db)
        self.daily_state_service = MMPlayerDailyStateService(db, self.config_service)
        self.scoring_service = MMScoringService(db)

    async def submit_caption(
        self,
        player: MMPlayer,
        image_id: UUID,
        text: str,
        shown_captions: list[MMCaption],
        transaction_service: TransactionService
    ) -> dict:
        """Submit a caption for an image.

        The backend automatically determines if the caption is a riff or original
        based on cosine similarity analysis of the shown captions.

        This method:
        1. Detects riffs algorithmically using cosine similarity
        2. Validates the caption text
        3. Checks free caption quota
        4. Charges submission fee if needed
        5. Creates caption and submission log
        6. Initializes quality score

        Args:
            player: Player submitting caption
            image_id: Image ID
            text: Caption text
            shown_captions: List of captions shown in the round (for riff detection)
            transaction_service: Transaction service

        Returns:
            Dictionary with submission results

        Raises:
            ValueError: Invalid caption
            InsufficientBalanceError: Player cannot afford submission fee
        """
        lock_name = f"submit_caption:{player.player_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Validate image exists and is active
            image = await self.db.get(MMImage, image_id)
            if not image or image.status != 'active':
                raise ValueError(f"Image {image_id} not found or inactive")

            # Detect riff or original using cosine similarity
            kind, parent_caption_id = await self._detect_riff_or_original(
                text, shown_captions
            )

            # Check if caption text is duplicate (basic check)
            await self._check_duplicate_caption(image_id, text)

            # Determine cost (free quota or paid)
            remaining_free = await self.daily_state_service.get_remaining_free_captions(
                player.player_id
            )
            used_free_slot = False
            cost = 0

            if remaining_free > 0:
                # Use free slot
                await self.daily_state_service.consume_free_caption(player.player_id)
                used_free_slot = True
                cost = 0
            else:
                # Charge submission fee
                cost = await self.config_service.get_config_value(
                    "mm_caption_submission_cost", default=10
                )

                if player.wallet < cost:
                    raise InsufficientBalanceError(
                        f"Insufficient balance. Need {cost}, have {player.wallet}"
                    )

                await transaction_service.create_transaction(
                    player.player_id,
                    -cost,
                    "mm_caption_submission_fee",
                    auto_commit=False,
                    skip_lock=True,
                )

            # Create caption
            caption = MMCaption(
                caption_id=uuid4(),
                image_id=image_id,
                author_player_id=player.player_id,
                kind=kind,
                parent_caption_id=parent_caption_id,
                text=text,
                status='active',
                created_at=datetime.now(UTC),
                shows=0,
                picks=0,
                first_vote_awarded=False,
                quality_score=self.scoring_service.calculate_quality_score(0, 0),
                lifetime_earnings_gross=0,
                lifetime_to_wallet=0,
                lifetime_to_vault=0,
            )

            self.db.add(caption)
            await self.db.flush([caption])

            # Create submission log
            submission = MMCaptionSubmission(
                submission_id=uuid4(),
                player_id=player.player_id,
                image_id=image_id,
                caption_id=caption.caption_id,
                submission_text=text,
                status='accepted',
                rejection_reason=None,
                used_free_slot=used_free_slot,
                created_at=datetime.now(UTC),
            )

            self.db.add(submission)
            await self.db.commit()
            await self.db.refresh(player)

            logger.info(
                f"Caption submitted: {caption.caption_id} by player {player.player_id} "
                f"for image {image_id}, kind={kind}, cost={cost}, free={used_free_slot}"
            )

            return {
                'success': True,
                'caption_id': caption.caption_id,
                'cost': cost,
                'used_free_slot': used_free_slot,
                'new_wallet': player.wallet,
                'quality_score': caption.quality_score,
            }

    async def _check_duplicate_caption(self, image_id: UUID, text: str) -> None:
        """Check if caption text already exists for this image.

        Args:
            image_id: Image ID
            text: Caption text to check

        Raises:
            ValueError: If duplicate caption exists
        """
        # Normalize text for comparison
        normalized_text = text.strip().lower()

        stmt = (
            select(MMCaption)
            .where(
                MMCaption.image_id == image_id,
                MMCaption.status == 'active',
                func.lower(func.trim(MMCaption.text)) == normalized_text
            )
            .limit(1)
        )

        from sqlalchemy import func
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError("This caption already exists for this image")

    async def _detect_riff_or_original(
        self,
        text: str,
        shown_captions: list[MMCaption]
    ) -> tuple[Literal["original", "riff"], UUID | None]:
        """Detect if a new caption is a riff or original using cosine similarity.

        Based on MM_GAME_RULES.md Section 5.2:
        - Compute cosine similarity between new caption and each shown caption
        - If max similarity > SIM_THRESHOLD (0.5), classify as riff with the caption
          having highest similarity as parent
        - Otherwise, classify as original

        Args:
            text: New caption text
            shown_captions: List of 5 captions shown in the round

        Returns:
            Tuple of (kind, parent_caption_id)
            - kind: "original" or "riff"
            - parent_caption_id: UUID if riff, None if original
        """
        if not shown_captions:
            # No captions to compare against, treat as original
            return "original", None

        # Get the phrase validator (uses sentence transformers for similarity)
        validator = get_phrase_validator()

        # Calculate cosine similarity to each shown caption
        similarities = []
        for caption in shown_captions:
            similarity = validator.calculate_similarity(text, caption.text)
            similarities.append((similarity, caption))

        # Find max similarity
        max_similarity, most_similar_caption = max(
            similarities, key=lambda x: x[0]
        )

        # Get SIM_THRESHOLD from config (default 0.5 per game rules)
        sim_threshold = await self.config_service.get_config_value(
            "mm_riff_similarity_threshold",
            default=0.5
        )

        logger.debug(
            f"Riff detection: text='{text[:50]}...', "
            f"max_sim={max_similarity:.3f}, threshold={sim_threshold}"
        )

        # Classify based on threshold
        if max_similarity > sim_threshold:
            return "riff", most_similar_caption.caption_id
        else:
            return "original", None

    async def _validate_riff_caption(
        self,
        text: str,
        parent_caption: MMCaption
    ) -> tuple[bool, str]:
        """Validate riff caption similarity to parent.

        Riffs should be different enough from parent to be interesting,
        but still related (enforced by parent reference).

        Args:
            text: Riff caption text
            parent_caption: Parent caption object

        Returns:
            (is_valid, error_message)
        """
        validator = get_phrase_validator()

        # Check basic format (length, characters)
        text_stripped = text.strip()
        if not text_stripped:
            return False, "Caption cannot be empty"
        if len(text_stripped) > 240:
            return False, "Caption must be 240 characters or less"

        # Check exact duplicate
        if text_stripped.lower() == parent_caption.text.strip().lower():
            return False, "Riff cannot be identical to parent caption"

        # Check similarity (use same threshold as QuipFlip copy phrases)
        similarity = validator.calculate_similarity(text, parent_caption.text)

        # Get threshold from config (default 0.7 like QuipFlip)
        threshold = await self.config_service.get_config_value(
            "mm_riff_similarity_threshold",
            default=0.7
        )

        if similarity >= threshold:
            return False, (
                f"Riff too similar to parent caption "
                f"(similarity: {similarity:.2f}, threshold: {threshold})"
            )

        return True, ""

    async def get_caption(self, caption_id: UUID) -> MMCaption | None:
        """Get a caption by ID.

        Args:
            caption_id: Caption ID

        Returns:
            Caption or None if not found
        """
        return await self.db.get(MMCaption, caption_id)

    async def get_captions_for_image(
        self,
        image_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> list[MMCaption]:
        """Get captions for an image.

        Args:
            image_id: Image ID
            limit: Maximum number of captions to return
            offset: Number of captions to skip

        Returns:
            List of captions
        """
        stmt = (
            select(MMCaption)
            .where(
                MMCaption.image_id == image_id,
                MMCaption.status == 'active'
            )
            .order_by(MMCaption.quality_score.desc(), MMCaption.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_player_captions(
        self,
        player_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> list[MMCaption]:
        """Get captions created by a player.

        Args:
            player_id: Player ID
            limit: Maximum number of captions to return
            offset: Number of captions to skip

        Returns:
            List of captions
        """
        stmt = (
            select(MMCaption)
            .where(MMCaption.author_player_id == player_id)
            .order_by(MMCaption.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
