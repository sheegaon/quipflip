"""IR Statistics Service - Player stats, metrics, and leaderboards."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.models.ir.backronym_entry import BackronymEntry
from backend.models.ir.backronym_vote import BackronymVote
from backend.models.ir.transaction import IRTransaction
from backend.models.ir.player import IRPlayer

logger = logging.getLogger(__name__)


class IRStatisticsError(RuntimeError):
    """Raised when statistics service fails."""


class IRStatisticsService:
    """Service for calculating player statistics and leaderboards."""

    def __init__(self, db: AsyncSession):
        """Initialize IR statistics service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_player_stats(self, player_id: str) -> dict:
        """Get comprehensive statistics for a player.

        Args:
            player_id: Player UUID

        Returns:
            dict: Player statistics including entries, votes, earnings
        """
        try:
            # Get player
            player_stmt = select(IRPlayer).where(IRPlayer.player_id == player_id)
            player_result = await self.db.execute(player_stmt)
            player = player_result.scalars().first()

            if not player:
                return {"error": "player_not_found"}

            # Count entries
            entries_stmt = select(func.count(BackronymEntry.entry_id)).where(
                (BackronymEntry.player_id == player_id)
                & (BackronymEntry.is_ai == False)
            )
            entries_result = await self.db.execute(entries_stmt)
            entry_count = entries_result.scalar() or 0

            # Count votes
            votes_stmt = select(func.count(BackronymVote.vote_id)).where(
                (BackronymVote.player_id == player_id)
                & (BackronymVote.is_ai == False)
            )
            votes_result = await self.db.execute(votes_stmt)
            vote_count = votes_result.scalar() or 0

            # Get transaction summary
            txn_stmt = (
                select(
                    IRTransaction.type,
                    func.count(IRTransaction.transaction_id),
                    func.sum(IRTransaction.amount),
                )
                .where(IRTransaction.player_id == player_id)
                .group_by(IRTransaction.type)
            )
            txn_result = await self.db.execute(txn_stmt)
            txn_rows = txn_result.all()

            txn_summary = {}
            total_earnings = 0
            total_expenses = 0

            for txn_type, count, total in txn_rows:
                txn_summary[txn_type] = {"count": count, "total": total or 0}

                # Calculate earnings/expenses
                if txn_type in ["ir_creator_payout", "ir_vote_payout", "daily_bonus"]:
                    total_earnings += total or 0
                elif txn_type in ["ir_backronym_entry", "ir_vote_cost"]:
                    total_expenses += abs(total or 0)

            return {
                "player_id": str(player_id),
                "username": player.username,
                "wallet": player.wallet,
                "vault": player.vault,
                "total_balance": player.wallet + player.vault,
                "is_guest": player.is_guest,
                "created_at": player.created_at.isoformat(),
                "last_login": player.last_login_date.isoformat()
                if player.last_login_date
                else None,
                "stats": {
                    "entries_submitted": entry_count,
                    "votes_cast": vote_count,
                    "total_earnings": total_earnings,
                    "total_expenses": total_expenses,
                    "net_earnings": total_earnings - total_expenses,
                },
                "transactions": txn_summary,
            }

        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            return {"error": str(e)}

    async def get_creator_leaderboard(self, limit: int = 10) -> list[dict]:
        """Get leaderboard ranked by creator vault contributions.

        Args:
            limit: Number of top creators to return

        Returns:
            list[dict]: Top creators with stats
        """
        try:
            # Get players ranked by vault
            stmt = (
                select(IRPlayer)
                .where(IRPlayer.is_ai == False)
                .order_by(IRPlayer.vault.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            players = result.scalars().all()

            leaderboard = []

            for rank, player in enumerate(players, 1):
                # Count entries for this player
                entries_stmt = select(func.count(BackronymEntry.entry_id)).where(
                    (BackronymEntry.player_id == str(player.player_id))
                    & (BackronymEntry.is_ai == False)
                )
                entries_result = await self.db.execute(entries_stmt)
                entry_count = entries_result.scalar() or 0

                leaderboard.append(
                    {
                        "rank": rank,
                        "player_id": str(player.player_id),
                        "username": player.username,
                        "vault": player.vault,
                        "wallet": player.wallet,
                        "total_balance": player.wallet + player.vault,
                        "entries_created": entry_count,
                    }
                )

            return leaderboard

        except Exception as e:
            logger.error(f"Error getting creator leaderboard: {e}")
            return []

    async def get_voter_leaderboard(self, limit: int = 10) -> list[dict]:
        """Get leaderboard ranked by voter vote accuracy.

        Args:
            limit: Number of top voters to return

        Returns:
            list[dict]: Top voters with stats
        """
        try:
            # Get all human voters with vote counts
            voter_stmt = (
                select(
                    BackronymVote.player_id,
                    func.count(BackronymVote.vote_id).label("vote_count"),
                )
                .where(
                    (BackronymVote.is_ai == False)
                    & (BackronymVote.is_participant_voter == False)
                )
                .group_by(BackronymVote.player_id)
                .order_by(func.count(BackronymVote.vote_id).desc())
                .limit(limit)
            )
            voter_result = await self.db.execute(voter_stmt)
            voters = voter_result.all()

            leaderboard = []

            for rank, (player_id, vote_count) in enumerate(voters, 1):
                # Get player info
                player_stmt = select(IRPlayer).where(IRPlayer.player_id == player_id)
                player_result = await self.db.execute(player_stmt)
                player = player_result.scalars().first()

                if player:
                    leaderboard.append(
                        {
                            "rank": rank,
                            "player_id": str(player.player_id),
                            "username": player.username,
                            "votes_cast": vote_count,
                            "wallet": player.wallet,
                            "vault": player.vault,
                        }
                    )

            return leaderboard

        except Exception as e:
            logger.error(f"Error getting voter leaderboard: {e}")
            return []

    async def get_set_statistics(self, set_id: str) -> dict:
        """Get statistics for a specific backronym set.

        Args:
            set_id: Set UUID

        Returns:
            dict: Set statistics
        """
        try:
            # Count entries
            entries_stmt = select(func.count(BackronymEntry.entry_id)).where(
                BackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entry_count = entries_result.scalar() or 0

            # Count votes
            votes_stmt = select(func.count(BackronymVote.vote_id)).where(
                BackronymVote.set_id == set_id
            )
            votes_result = await self.db.execute(votes_stmt)
            vote_count = votes_result.scalar() or 0

            # Count human vs AI
            human_entries_stmt = select(func.count(BackronymEntry.entry_id)).where(
                (BackronymEntry.set_id == set_id)
                & (BackronymEntry.is_ai == False)
            )
            human_entries_result = await self.db.execute(human_entries_stmt)
            human_entries = human_entries_result.scalar() or 0

            ai_entries = entry_count - human_entries

            human_votes_stmt = select(func.count(BackronymVote.vote_id)).where(
                (BackronymVote.set_id == set_id)
                & (BackronymVote.is_ai == False)
            )
            human_votes_result = await self.db.execute(human_votes_stmt)
            human_votes = human_votes_result.scalar() or 0

            ai_votes = vote_count - human_votes

            return {
                "set_id": set_id,
                "entries": {
                    "total": entry_count,
                    "human": human_entries,
                    "ai": ai_entries,
                },
                "votes": {
                    "total": vote_count,
                    "human": human_votes,
                    "ai": ai_votes,
                },
            }

        except Exception as e:
            logger.error(f"Error getting set statistics: {e}")
            return {"set_id": set_id}

    async def get_global_statistics(self) -> dict:
        """Get global IR game statistics.

        Returns:
            dict: Global statistics
        """
        try:
            # Total players
            players_stmt = select(func.count(IRPlayer.player_id)).where(
                IRPlayer.is_ai == False
            )
            players_result = await self.db.execute(players_stmt)
            total_players = players_result.scalar() or 0

            # Total entries
            entries_stmt = select(func.count(BackronymEntry.entry_id)).where(
                BackronymEntry.is_ai == False
            )
            entries_result = await self.db.execute(entries_stmt)
            total_entries = entries_result.scalar() or 0

            # Total votes
            votes_stmt = select(func.count(BackronymVote.vote_id)).where(
                BackronymVote.is_ai == False
            )
            votes_result = await self.db.execute(votes_stmt)
            total_votes = votes_result.scalar() or 0

            # Total vault
            vault_stmt = select(func.sum(IRPlayer.vault)).where(
                IRPlayer.is_ai == False
            )
            vault_result = await self.db.execute(vault_stmt)
            total_vault = vault_result.scalar() or 0

            return {
                "total_players": total_players,
                "total_entries": total_entries,
                "total_votes": total_votes,
                "total_vault": total_vault,
            }

        except Exception as e:
            logger.error(f"Error getting global statistics: {e}")
            return {}
