"""IR Scoring Service - Prize pool calculation and payout logic."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.backronym_set import BackronymSet
from backend.models.ir.backronym_entry import BackronymEntry
from backend.models.ir.backronym_vote import BackronymVote
from backend.models.ir.result_view import IRResultView
from backend.services.transaction_service import TransactionService
from backend.services.auth_service import GameType
from backend.utils.exceptions import InsufficientBalanceError

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
        self.transaction_service = TransactionService(db, game_type=GameType.IR)

    async def calculate_payouts(self, set_id: str) -> dict:
        """Calculate all payouts for a finalized set.

        Enforces creator vote requirement: creators must vote to receive payout.
        Otherwise, their share is forfeited to the vault.

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
                - forfeited_entries: List of entry IDs forfeited to vault
                - vault_contributions: Dict of player_id -> vault amount
                - payouts_processed: Whether payouts have been applied

        Raises:
            IRScoringError: If calculation fails
        """
        try:
            # Get set
            stmt = select(BackronymSet).where(BackronymSet.set_id == set_id)
            result = await self.db.execute(stmt)
            set_obj = result.scalars().first()

            if not set_obj:
                raise IRScoringError("set_not_found")

            # Get entries
            entries_stmt = select(BackronymEntry).where(
                BackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            # Get votes
            votes_stmt = select(BackronymVote).where(BackronymVote.set_id == set_id)
            votes_result = await self.db.execute(votes_stmt)
            votes = votes_result.scalars().all()

            # Calculate entry costs (100 IC per human entry)
            human_entries = [e for e in entries if not e.is_ai]
            entry_costs = len(human_entries) * self.settings.ir_backronym_entry_cost

            # Calculate vote costs (10 IC per non-participant vote)
            non_participant_votes = [
                v for v in votes if not v.is_participant_voter and not v.is_ai
            ]
            vote_contributions = len(non_participant_votes) * self.settings.ir_vote_cost

            # Total pool = entry costs + vote costs from non-participants
            total_pool = entry_costs + vote_contributions

            # Find winning entry (most votes)
            winning_entry = max(entries, key=lambda e: e.received_votes)
            vote_winner_count = winning_entry.received_votes

            # Get all voters and determine winners
            voter_payouts = {}

            # Process non-participant voters (correct voters get 20 IC each)
            non_participant_correct_voters = [
                v for v in non_participant_votes
                if v.chosen_entry_id == winning_entry.entry_id
            ]

            non_participant_payout_per_winner = self.settings.ir_vote_reward_correct
            non_participant_payouts_paid = (
                len(non_participant_correct_voters) * non_participant_payout_per_winner
            )

            for voter in non_participant_correct_voters:
                voter_payouts[str(voter.player_id)] = non_participant_payout_per_winner
                # Mark vote as correct for non-participants
                for vote in votes:
                    if (
                        str(vote.player_id) == str(voter.player_id)
                        and not vote.is_participant_voter
                    ):
                        vote.is_correct_popular = True

            # Remaining pool for creators (after non-participant payouts)
            creator_final_pool = total_pool - non_participant_payouts_paid

            # Check which creators voted
            creator_votes = {}
            for vote in votes:
                if vote.is_participant_voter:
                    creator_votes[str(vote.player_id)] = True

            # Distribute creator pool pro-rata based on votes received
            # BUT only to creators who cast votes
            total_votes_for_creators = sum(e.received_votes for e in entries)
            creator_payouts_dict = {}
            forfeited_entries = []
            total_forfeited = 0

            if total_votes_for_creators > 0:
                for entry in entries:
                    creator_id = str(entry.player_id)
                    share_pct = (
                        (entry.received_votes / total_votes_for_creators) * 100
                        if total_votes_for_creators > 0
                        else 0
                    )

                    # Update entry with vote share percentage
                    entry.vote_share_pct = int(share_pct)

                    # Check if creator voted
                    creator_voted = creator_id in creator_votes

                    if entry.received_votes > 0 and creator_voted:
                        creator_payout = int(
                            creator_final_pool * (entry.received_votes / total_votes_for_creators)
                        )

                        # Apply 30% vault rake to creator payout
                        vault_rake_pct = self.settings.ir_vault_rake_percent  # 30%
                        vault_rake = int(creator_payout * (vault_rake_pct / 100))
                        net_payout = creator_payout - vault_rake

                        creator_payouts_dict[creator_id] = {
                            "amount": net_payout,
                            "vault_contribution": vault_rake,
                            "vote_share_pct": int(share_pct),
                        }
                    elif entry.received_votes > 0 and not creator_voted:
                        # Creator didn't vote - forfeit to vault
                        entry.forfeited_to_vault = True
                        forfeited_entries.append(str(entry.entry_id))
                        forfeited_amount = int(
                            creator_final_pool * (entry.received_votes / total_votes_for_creators)
                        )
                        total_forfeited += forfeited_amount
                        logger.info(
                            f"Creator {creator_id} for entry {entry.entry_id} did not vote - "
                            f"forfeiting {forfeited_amount} to vault"
                        )

            # Update set with pool totals
            set_obj.total_pool = total_pool
            set_obj.vote_contributions = vote_contributions
            set_obj.non_participant_payouts_paid = non_participant_payouts_paid
            set_obj.creator_final_pool = creator_final_pool

            # Flush changes to make them visible in current transaction
            # but don't commit yet - commit happens in process_payouts
            await self.db.flush()

            return {
                "set_id": set_id,
                "total_pool": total_pool,
                "entry_costs": entry_costs,
                "vote_contributions": vote_contributions,
                "non_participant_payouts_paid": non_participant_payouts_paid,
                "creator_final_pool": creator_final_pool,
                "winning_entry_id": str(winning_entry.entry_id),
                "winning_entry_creator": str(winning_entry.player_id),
                "vote_winner_count": vote_winner_count,
                "human_entries_count": len(human_entries),
                "non_participant_votes_count": len(non_participant_votes),
                "non_participant_correct_voters": len(non_participant_correct_voters),
                "non_participant_payout_each": non_participant_payout_per_winner,
                "voter_payouts": voter_payouts,
                "creator_payouts": creator_payouts_dict,
                "forfeited_entries": forfeited_entries,
                "total_forfeited_to_vault": total_forfeited,
                "total_distributed": non_participant_payouts_paid + sum(
                    p["amount"] for p in creator_payouts_dict.values()
                ),
            }

        except IRScoringError:
            raise
        except Exception as e:
            raise IRScoringError(f"Failed to calculate payouts: {str(e)}") from e

    async def process_payouts(self, set_id: str) -> dict:
        """Process and apply payouts for a finalized set.

        Includes vault contributions from creator payouts and forfeited amounts.

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
                "vault_transactions": [],
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
                except InsufficientBalanceError as e:
                    logger.error(f"Failed to process voter payout: {e}")
                    results["voter_transactions"].append(
                        {
                            "player_id": voter_id,
                            "amount": amount,
                            "error": str(e),
                        }
                    )

            # Process creator payouts (net after vault rake)
            for creator_id, payout_info in payouts["creator_payouts"].items():
                net_amount = payout_info["amount"]
                vault_contribution = payout_info["vault_contribution"]

                try:
                    # Pay creator the net amount
                    txn = await self.transaction_service.process_creator_payout(
                        player_id=creator_id, amount=net_amount, set_id=set_id
                    )
                    results["creator_transactions"].append(
                        {
                            "player_id": creator_id,
                            "amount": net_amount,
                            "vault_contribution": vault_contribution,
                            "transaction_id": str(txn.transaction_id),
                        }
                    )

                    # Record vault contribution from this creator
                    # Note: The vault rake was already subtracted from net_amount,
                    # so we just credit the vault directly (not debit wallet again)
                    if vault_contribution > 0:
                        vault_txn = await self.transaction_service.credit_vault(
                            player_id=creator_id,
                            amount=vault_contribution,
                            transaction_type=self.transaction_service.VAULT_CONTRIBUTION,
                            reference_id=set_id,
                        )
                        results["vault_transactions"].append(
                            {
                                "player_id": creator_id,
                                "amount": vault_contribution,
                                "transaction_id": str(vault_txn.transaction_id),
                            }
                        )

                except InsufficientBalanceError as e:
                    logger.error(f"Failed to process creator payout: {e}")
                    results["creator_transactions"].append(
                        {
                            "player_id": creator_id,
                            "amount": net_amount,
                            "vault_contribution": vault_contribution,
                            "error": str(e),
                        }
                    )

            # Emit ResultView records per creator for claim flow
            # This ensures that creators can view their results
            entries_stmt = select(BackronymEntry).where(
                BackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            for entry in entries:
                creator_id = str(entry.player_id)

                # Check if ResultView already exists for this creator
                result_view_stmt = select(IRResultView).where(
                    (IRResultView.set_id == set_id)
                    & (IRResultView.player_id == creator_id)
                )
                result_view_result = await self.db.execute(result_view_stmt)
                existing_view = result_view_result.scalars().first()

                if not existing_view:
                    # Get payout amount for this creator
                    payout_amount = 0
                    if creator_id in payouts.get("creator_payouts", {}):
                        payout_amount = payouts["creator_payouts"][creator_id]["amount"]

                    # Create ResultView record
                    result_view = IRResultView(
                        set_id=set_id,
                        player_id=creator_id,
                        result_viewed=False,  # Not viewed yet
                        payout_amount=payout_amount,
                        viewed_at=None,
                        first_viewed_at=None,
                    )
                    self.db.add(result_view)

                    logger.info(
                        f"Created ResultView for creator {creator_id} on set {set_id}, "
                        f"payout: {payout_amount}"
                    )

            await self.db.commit()

            logger.info(
                f"Processed payouts for set {set_id}: "
                f"{len(results['voter_transactions'])} voter payouts, "
                f"{len(results['creator_transactions'])} creator payouts, "
                f"{len(results['vault_transactions'])} vault contributions"
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
