"""IR Result View Service - Result claiming and payout tracking."""

import logging
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.result_view import IRResultView
from backend.models.ir.backronym_set import BackronymSet
from backend.models.ir.enums import SetStatus
from backend.services.ir.scoring_service import IRScoringService, IRScoringError

logger = logging.getLogger(__name__)


class IRResultViewError(RuntimeError):
    """Raised when result view service fails."""


class IRResultViewService:
    """Service for managing result views and payout claiming."""

    def __init__(self, db: AsyncSession):
        """Initialize IR result view service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.scoring_service = IRScoringService(db)

    async def claim_result(
        self, player_id: str, set_id: str
    ) -> dict:
        """Claim result for a player on a set (idempotent).

        Marks result as viewed and retrieves any payout information.

        Args:
            player_id: Player UUID
            set_id: Set UUID

        Returns:
            dict: Result info including payout amount

        Raises:
            IRResultViewError: If result claiming fails
        """
        try:
            # Get set
            set_stmt = select(BackronymSet).where(BackronymSet.set_id == set_id)
            set_result = await self.db.execute(set_stmt)
            set_obj = set_result.scalars().first()

            if not set_obj:
                raise IRResultViewError("set_not_found")

            if set_obj.status != SetStatus.FINALIZED:
                raise IRResultViewError("set_not_finalized")

            # Check if result already claimed
            result_view_stmt = select(IRResultView).where(
                (IRResultView.set_id == set_id) & (IRResultView.player_id == player_id)
            )
            result_view_result = await self.db.execute(result_view_stmt)
            result_view = result_view_result.scalars().first()

            if not result_view:
                # First time viewing result
                # Try to calculate payout
                try:
                    payouts = await self.scoring_service.calculate_payouts(set_id)

                    payout_amount = 0
                    payout_source = None

                    # Check if player got voter payout
                    if str(player_id) in payouts.get("voter_payouts", {}):
                        payout_amount = payouts["voter_payouts"][str(player_id)]
                        payout_source = "voter"
                    # Check if player got creator payout
                    elif str(player_id) in payouts.get("creator_payouts", {}):
                        payout_info = payouts["creator_payouts"][str(player_id)]
                        payout_amount = payout_info.get("amount", 0)
                        payout_source = "creator"

                except IRScoringError:
                    payout_amount = 0
                    payout_source = None

                # Create result view record
                result_view = IRResultView(
                    set_id=set_id,
                    player_id=player_id,
                    result_viewed=True,
                    payout_amount=payout_amount,
                    viewed_at=datetime.now(UTC),
                    first_viewed_at=datetime.now(UTC),
                )
                self.db.add(result_view)
                await self.db.commit()
                await self.db.refresh(result_view)

                logger.info(
                    f"Claimed result for player {player_id} on set {set_id}, payout: {payout_amount}"
                )
            else:
                # Already claimed, just update last viewed
                payout_amount = result_view.payout_amount
                result_view.result_viewed = True
                result_view.viewed_at = datetime.now(UTC)
                await self.db.commit()

            # Get set details for display
            set_details = await self._get_set_result_details(set_id)

            return {
                "set_id": set_id,
                "word": set_obj.word,
                "payout_amount": payout_amount,
                "first_viewed_at": result_view.first_viewed_at.isoformat()
                if result_view.first_viewed_at
                else None,
                "latest_viewed_at": result_view.viewed_at.isoformat()
                if result_view.viewed_at
                else None,
                "entries": set_details.get("entries", []),
                "winning_entry_id": set_details.get("winning_entry_id"),
            }

        except IRResultViewError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRResultViewError(f"Failed to claim result: {str(e)}") from e

    async def get_pending_results(self, player_id: str) -> list[dict]:
        """Get unclaimed/pending results for a player.

        Args:
            player_id: Player UUID

        Returns:
            list[dict]: Pending results
        """
        try:
            # Get all finalized sets
            sets_stmt = select(BackronymSet).where(
                BackronymSet.status == SetStatus.FINALIZED
            )
            sets_result = await self.db.execute(sets_stmt)
            finalized_sets = sets_result.scalars().all()

            pending = []

            for set_obj in finalized_sets:
                # Check if player has result view record
                result_view_stmt = select(IRResultView).where(
                    (IRResultView.set_id == str(set_obj.set_id))
                    & (IRResultView.player_id == player_id)
                )
                result_view_result = await self.db.execute(result_view_stmt)
                result_view = result_view_result.scalars().first()

                # Show as pending if no result view or not fully viewed
                if not result_view or not result_view.result_viewed:
                    try:
                        payouts = await self.scoring_service.calculate_payouts(
                            str(set_obj.set_id)
                        )

                        payout_amount = 0

                        if str(player_id) in payouts.get("voter_payouts", {}):
                            payout_amount = payouts["voter_payouts"][str(player_id)]
                        elif str(player_id) in payouts.get("creator_payouts", {}):
                            payout_info = payouts["creator_payouts"][str(player_id)]
                            payout_amount = payout_info.get("amount", 0)

                        if payout_amount > 0:
                            pending.append(
                                {
                                    "set_id": str(set_obj.set_id),
                                    "word": set_obj.word,
                                    "payout_amount": payout_amount,
                                    "finalized_at": set_obj.finalized_at.isoformat(),
                                }
                            )
                    except IRScoringError:
                        logger.warning(f"Could not calculate payouts for set {set_obj.set_id}")

            return pending

        except Exception as e:
            logger.error(f"Error getting pending results: {e}")
            return []

    async def get_result_details(self, player_id: str, set_id: str) -> dict:
        """Get detailed result information for a player on a set.

        Args:
            player_id: Player UUID
            set_id: Set UUID

        Returns:
            dict: Detailed result info

        Raises:
            IRResultViewError: If retrieval fails
        """
        try:
            # Claim result first (idempotent)
            result = await self.claim_result(player_id, set_id)

            # Get more details
            try:
                payouts = await self.scoring_service.calculate_payouts(set_id)
                result["full_payouts"] = payouts
            except IRScoringError:
                pass

            return result

        except IRResultViewError:
            raise
        except Exception as e:
            raise IRResultViewError(f"Failed to get result details: {str(e)}") from e

    async def _get_set_result_details(self, set_id: str) -> dict:
        """Get set result details for display.

        Args:
            set_id: Set UUID

        Returns:
            dict: Set result details
        """
        try:
            payouts = await self.scoring_service.calculate_payouts(set_id)

            winning_entry_id = payouts.get("winning_entry_id")

            return {
                "set_id": set_id,
                "winning_entry_id": winning_entry_id,
                "entries": payouts.get("entries", []),
                "total_pool": payouts.get("total_pool", 0),
                "vault_rake": payouts.get("vault_rake_amount", 0),
            }

        except IRScoringError:
            return {"set_id": set_id}
        except Exception as e:
            logger.error(f"Error getting set result details: {e}")
            return {"set_id": set_id}
