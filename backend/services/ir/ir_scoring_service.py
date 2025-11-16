"""IR Scoring Service - Prize pool calculation and payout logic."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.ir_backronym_entry import IRBackronymEntry
from backend.models.ir.ir_backronym_vote import IRBackronymVote
from backend.models.ir.enums import IRSetStatus
from backend.services.ir.ir_transaction_service import (
    IRTransactionService,
    IRTransactionError,
)

logger = logging.getLogger(__name__)


class IRScoringError(RuntimeError):
    """Raised when scoring service fails."""


class IRScoringService:
    """Service for calculating prize pools and determining payouts."""

    def __init__(self, db: AsyncSession):
        """Initialize IR scoring service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.transaction_service = IRTransactionService(db)

    async def calculate_payouts(self, set_id: str) -> dict:
        """Calculate all payouts for a finalized set.

        Args:
            set_id: Set UUID

        Returns:
            dict: Payout information with:
                - set_id: The set ID
                - total_pool: Total amount from entry costs and vote costs
                - entry_costs: Total from entry submissions (100 IC each)
                - vote_costs: Total from votes (10 IC each)
                - winning_entry_id: ID of entry with most votes
                - vote_winner_count: Number of votes for winning entry
                - creator_payouts: Dict of creator_id -> amount
                - voter_payouts: Dict of voter_id -> amount
                - vault_contributions: Dict of player_id -> vault amount
                - payouts_processed: Whether payouts have been applied

        Raises:
            IRScoringError: If calculation fails
        """
        try:
            # Get set
            stmt = select(IRBackronymSet).where(IRBackronymSet.set_id == set_id)
            result = await self.db.execute(stmt)
            set_obj = result.scalars().first()

            if not set_obj:
                raise IRScoringError("set_not_found")

            # Get entries
            entries_stmt = select(IRBackronymEntry).where(
                IRBackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            # Get votes
            votes_stmt = select(IRBackronymVote).where(IRBackronymVote.set_id == set_id)
            votes_result = await self.db.execute(votes_stmt)
            votes = votes_result.scalars().all()

            # Calculate entry costs (100 IC per human entry)
            human_entries = [e for e in entries if not e.is_ai]
            entry_costs = len(human_entries) * self.settings.ir_backronym_entry_cost

            # Calculate vote costs (10 IC per vote)
            human_votes = [v for v in votes if not v.is_ai]
            vote_costs = len(human_votes) * self.settings.ir_vote_cost

            # Total pool = entry costs + vote costs
            total_pool = entry_costs + vote_costs

            # Find winning entry (most votes)
            winning_entry = max(entries, key=lambda e: e.received_votes)
            vote_winner_count = winning_entry.received_votes

            # Calculate payouts
            vault_rake_pct = self.settings.ir_vault_rake_percent  # 30%
            vault_rake = int(total_pool * (vault_rake_pct / 100))
            remaining_pool = total_pool - vault_rake

            # Get all voters and determine winners
            voter_payouts = {}
            creator_payouts = {}

            # Process non-participant voters (correct voters get 20 IC each)
            non_participant_voters = [
                v for v in votes if not v.is_participant_voter and not v.is_ai
            ]
            non_participant_correct_voters = [
                v for v in non_participant_voters
                if v.chosen_entry_id == winning_entry.entry_id
            ]

            non_participant_payout_per_winner = self.settings.ir_vote_reward_correct
            non_participant_total_payout = (
                len(non_participant_correct_voters) * non_participant_payout_per_winner
            )

            for voter in non_participant_correct_voters:
                voter_payouts[str(voter.player_id)] = non_participant_payout_per_winner

            # Remaining pool for creators (after non-participant payouts)
            creator_pool = remaining_pool - non_participant_total_payout

            # Distribute creator pool pro-rata based on votes received
            total_votes_for_creators = sum(e.received_votes for e in entries)
            creator_payouts_dict = {}

            if total_votes_for_creators > 0:
                for entry in entries:
                    if entry.received_votes > 0:
                        share_pct = (
                            entry.received_votes / total_votes_for_creators
                        ) * 100
                        creator_payout = int(
                            creator_pool * (entry.received_votes / total_votes_for_creators)
                        )
                        creator_payouts_dict[str(entry.player_id)] = {
                            "amount": creator_payout,
                            "vote_share_pct": int(share_pct),
                        }

            # Calculate vault contributions (rake collected from payouts)
            # Non-participant payouts don't have rake
            creator_vault_rake = vault_rake
            participant_vault_rake = {}

            for creator_id, payout_info in creator_payouts_dict.items():
                creator_payout = payout_info["amount"]
                # Apply rake to creator payouts
                creator_rake = int(creator_payout * (vault_rake_pct / 100))
                # Actually, rake is already calculated from entry/vote costs
                # Creator gets their share of remaining pool
                participant_vault_rake[creator_id] = 0  # Rake already in creator_vault_rake

            return {
                "set_id": set_id,
                "total_pool": total_pool,
                "entry_costs": entry_costs,
                "vote_costs": vote_costs,
                "vault_rake_amount": vault_rake,
                "remaining_pool_after_rake": remaining_pool,
                "winning_entry_id": str(winning_entry.entry_id),
                "winning_entry_creator": str(winning_entry.player_id),
                "vote_winner_count": vote_winner_count,
                "human_entries_count": len(human_entries),
                "human_votes_count": len(human_votes),
                "non_participant_correct_voters": len(non_participant_correct_voters),
                "non_participant_payout_each": non_participant_payout_per_winner,
                "non_participant_total_payout": non_participant_total_payout,
                "creator_pool": creator_pool,
                "voter_payouts": voter_payouts,
                "creator_payouts": creator_payouts_dict,
                "total_distributed": non_participant_total_payout + sum(
                    p["amount"] for p in creator_payouts_dict.values()
                ),
            }

        except IRScoringError:
            raise
        except Exception as e:
            raise IRScoringError(f"Failed to calculate payouts: {str(e)}") from e

    async def process_payouts(self, set_id: str) -> dict:
        """Process and apply payouts for a finalized set.

        Args:
            set_id: Set UUID

        Returns:
            dict: Payout processing results with transaction IDs

        Raises:
            IRScoringError: If payout processing fails
        """
        try:
            # Calculate payouts
            payouts = await self.calculate_payouts(set_id)

            results = {
                "set_id": set_id,
                "voter_transactions": [],
                "creator_transactions": [],
            }

            # Process non-participant voter payouts
            for voter_id, amount in payouts["voter_payouts"].items():
                try:
                    txn = await self.transaction_service.process_vote_payout(
                        player_id=voter_id, amount=amount, set_id=set_id
                    )
                    results["voter_transactions"].append(
                        {
                            "player_id": voter_id,
                            "amount": amount,
                            "transaction_id": str(txn.transaction_id),
                        }
                    )
                except IRTransactionError as e:
                    logger.error(f"Failed to process voter payout: {e}")
                    results["voter_transactions"].append(
                        {
                            "player_id": voter_id,
                            "amount": amount,
                            "error": str(e),
                        }
                    )

            # Process creator payouts
            for creator_id, payout_info in payouts["creator_payouts"].items():
                amount = payout_info["amount"]
                try:
                    txn = await self.transaction_service.process_creator_payout(
                        player_id=creator_id, amount=amount, set_id=set_id
                    )
                    results["creator_transactions"].append(
                        {
                            "player_id": creator_id,
                            "amount": amount,
                            "transaction_id": str(txn.transaction_id),
                        }
                    )
                except IRTransactionError as e:
                    logger.error(f"Failed to process creator payout: {e}")
                    results["creator_transactions"].append(
                        {
                            "player_id": creator_id,
                            "amount": amount,
                            "error": str(e),
                        }
                    )

            logger.info(
                f"Processed payouts for set {set_id}: "
                f"{len(results['voter_transactions'])} voter payouts, "
                f"{len(results['creator_transactions'])} creator payouts"
            )
            return results

        except IRScoringError:
            raise
        except Exception as e:
            raise IRScoringError(f"Failed to process payouts: {str(e)}") from e

    async def get_payout_summary(self, set_id: str) -> dict:
        """Get summary of payouts for display purposes.

        Args:
            set_id: Set UUID

        Returns:
            dict: Summary of all payouts
        """
        try:
            payouts = await self.calculate_payouts(set_id)

            total_payouts = payouts.get("total_distributed", 0)
            total_vault = payouts.get("vault_rake_amount", 0)

            return {
                "set_id": set_id,
                "total_pool": payouts.get("total_pool", 0),
                "vault_contribution": total_vault,
                "total_distributed_to_players": total_payouts,
                "winner_entry_id": payouts.get("winning_entry_id"),
                "voter_payout_count": len(payouts.get("voter_payouts", {})),
                "creator_payout_count": len(payouts.get("creator_payouts", {})),
            }

        except Exception as e:
            logger.error(f"Failed to get payout summary: {e}")
            return {}
