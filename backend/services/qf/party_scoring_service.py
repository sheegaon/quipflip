"""Party Mode scoring service for calculating match results and awards."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Dict, List
from uuid import UUID
import logging

from backend.models.qf.party_session import PartySession
from backend.models.qf.party_participant import PartyParticipant
from backend.models.qf.party_round import PartyRound
from backend.models.qf.party_phraseset import PartyPhraseset
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.vote import Vote
from backend.models.qf.transaction import QFTransaction
from backend.models.qf.player import QFPlayer
from backend.services.qf.party_session_service import SessionNotFoundError, PartyModeError

logger = logging.getLogger(__name__)


class PartyScoringService:
    """Service for calculating party session results and awards."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_session_results(self, session_id: UUID) -> Dict:
        """Calculate comprehensive session results including rankings and awards.

        Args:
            session_id: UUID of the session

        Returns:
            dict: Complete session results with rankings, awards, and statistics

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        # Get session
        result = await self.db.execute(
            select(PartySession).where(PartySession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Get all participants with player info
        result = await self.db.execute(
            select(PartyParticipant, QFPlayer)
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(PartyParticipant.session_id == session_id)
        )
        participants_data = result.all()

        if not participants_data:
            return {
                'session_id': str(session_id),
                'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                'rankings': [],
                'awards': {},
                'phrasesets_summary': [],
            }

        # Get all party rounds for this session
        result = await self.db.execute(
            select(PartyRound)
            .where(PartyRound.session_id == session_id)
        )
        party_rounds = result.scalars().all()
        round_ids = [pr.round_id for pr in party_rounds]

        # Get all transactions for these rounds
        result = await self.db.execute(
            select(QFTransaction)
            .where(
                or_(
                    QFTransaction.reference_id.in_(round_ids),
                    QFTransaction.type.in_(['prize_payout', 'vote_payout'])
                )
            )
        )
        all_transactions = result.scalars().all()

        # Get all party phrasesets
        result = await self.db.execute(
            select(PartyPhraseset, Phraseset)
            .join(Phraseset, PartyPhraseset.phraseset_id == Phraseset.phraseset_id)
            .where(PartyPhraseset.session_id == session_id)
        )
        party_phrasesets_data = result.all()
        party_phrasesets = [pp for pp, _ in party_phrasesets_data]
        phrasesets = {pp.phraseset_id: phraseset for pp, phraseset in party_phrasesets_data}

        # Calculate per-player statistics
        player_stats = {}
        for participant, player in participants_data:
            player_id = participant.player_id

            # Get rounds for this player
            player_party_rounds = [pr for pr in party_rounds if pr.participant_id == participant.participant_id]
            player_round_ids = [pr.round_id for pr in player_party_rounds]

            # Calculate coins spent (entry costs are negative)
            spent_transactions = [
                txn for txn in all_transactions
                if txn.player_id == player_id
                and txn.type in ['prompt_entry', 'copy_entry', 'vote_entry']
                and txn.reference_id in player_round_ids
            ]
            spent = sum(abs(txn.amount) for txn in spent_transactions)

            # Calculate coins earned (payouts are positive)
            # Need to check both round_ids and phraseset_ids
            phraseset_ids = [pp.phraseset_id for pp in party_phrasesets]

            earned_transactions = [
                txn for txn in all_transactions
                if txn.player_id == player_id
                and txn.type in ['vote_payout', 'prize_payout']
                and (txn.reference_id in player_round_ids or txn.reference_id in phraseset_ids)
            ]
            earned = sum(txn.amount for txn in earned_transactions)

            # Net coins
            net = earned - spent

            # Get phrasesets where this player was prompt contributor
            prompt_phrasesets = [
                phrasesets[pp.phraseset_id]
                for pp in party_phrasesets
                if pp.phraseset_id in phrasesets
                and phrasesets[pp.phraseset_id].prompt_round_id in player_round_ids
            ]

            # Count votes received on originals
            votes_on_originals = 0
            for ps in prompt_phrasesets:
                result = await self.db.execute(
                    select(func.count(Vote.vote_id))
                    .where(Vote.phraseset_id == ps.phraseset_id)
                    .where(Vote.voted_phrase == ps.original_phrase)
                )
                votes_on_originals += result.scalar() or 0

            # Get phrasesets where this player was copy contributor
            copy_phrasesets = []
            for pp in party_phrasesets:
                if pp.phraseset_id in phrasesets:
                    ps = phrasesets[pp.phraseset_id]
                    if ps.copy_round_1_id in player_round_ids or ps.copy_round_2_id in player_round_ids:
                        copy_phrasesets.append(ps)

            # Count votes fooled (votes on this player's copies)
            votes_fooled = 0
            for ps in copy_phrasesets:
                # Check if player submitted copy1
                if ps.copy_round_1_id in player_round_ids:
                    result = await self.db.execute(
                        select(func.count(Vote.vote_id))
                        .where(Vote.phraseset_id == ps.phraseset_id)
                        .where(Vote.voted_phrase == ps.copy_phrase_1)
                    )
                    votes_fooled += result.scalar() or 0

                # Check if player submitted copy2
                if ps.copy_round_2_id in player_round_ids:
                    result = await self.db.execute(
                        select(func.count(Vote.vote_id))
                        .where(Vote.phraseset_id == ps.phraseset_id)
                        .where(Vote.voted_phrase == ps.copy_phrase_2)
                    )
                    votes_fooled += result.scalar() or 0

            # Get votes by this player
            result = await self.db.execute(
                select(Vote)
                .where(Vote.round_id.in_(player_round_ids))
                .where(Vote.phraseset_id.in_(phraseset_ids))
            )
            player_votes = result.scalars().all()

            correct_votes = sum(1 for v in player_votes if v.correct)
            total_votes = len(player_votes)
            vote_accuracy = (correct_votes / total_votes * 100) if total_votes > 0 else 0

            player_stats[player_id] = {
                'player_id': str(player_id),
                'username': player.username,
                'spent': spent,
                'earned': earned,
                'net': net,
                'votes_on_originals': votes_on_originals,
                'votes_fooled': votes_fooled,
                'correct_votes': correct_votes,
                'total_votes': total_votes,
                'vote_accuracy': round(vote_accuracy, 1),
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
            }

        # Calculate rankings (by net coins)
        rankings = sorted(
            player_stats.values(),
            key=lambda x: x['net'],
            reverse=True
        )
        for i, player in enumerate(rankings):
            player['rank'] = i + 1

        # Calculate awards
        awards = {}

        # Best Writer - most votes on originals
        if any(p['votes_on_originals'] > 0 for p in player_stats.values()):
            best_writer = max(player_stats.values(), key=lambda x: x['votes_on_originals'])
            awards['best_writer'] = {
                'player_id': best_writer['player_id'],
                'username': best_writer['username'],
                'votes_received': best_writer['votes_on_originals'],
                'metric_value': best_writer['votes_on_originals'],
            }

        # Top Impostor - most votes fooled by copies
        if any(p['votes_fooled'] > 0 for p in player_stats.values()):
            top_impostor = max(player_stats.values(), key=lambda x: x['votes_fooled'])
            awards['top_impostor'] = {
                'player_id': top_impostor['player_id'],
                'username': top_impostor['username'],
                'votes_fooled': top_impostor['votes_fooled'],
                'metric_value': top_impostor['votes_fooled'],
            }

        # Sharpest Voter - best vote accuracy
        voters_with_votes = [p for p in player_stats.values() if p['total_votes'] > 0]
        if voters_with_votes:
            sharpest_voter = max(voters_with_votes, key=lambda x: x['vote_accuracy'])
            awards['sharpest_voter'] = {
                'player_id': sharpest_voter['player_id'],
                'username': sharpest_voter['username'],
                'vote_accuracy': sharpest_voter['vote_accuracy'],
                'metric_value': sharpest_voter['vote_accuracy'],
            }

        # Get phraseset summaries
        phraseset_summaries = await self._get_phraseset_summaries(session_id, phrasesets, party_rounds)

        return {
            'session_id': str(session_id),
            'party_code': session.party_code,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'rankings': rankings,
            'awards': awards,
            'phrasesets_summary': phraseset_summaries,
        }

    async def _get_phraseset_summaries(
        self,
        session_id: UUID,
        phrasesets: Dict[UUID, Phraseset],
        party_rounds: List[PartyRound],
    ) -> List[Dict]:
        """Get summaries of all phrasesets in the session.

        Args:
            session_id: UUID of the session
            phrasesets: Dict mapping phraseset_id to Phraseset objects
            party_rounds: List of party rounds

        Returns:
            List[dict]: Phraseset summaries
        """
        summaries = []

        for phraseset_id, ps in phrasesets.items():
            # Get prompt player username
            prompt_round_id = ps.prompt_round_id
            prompt_party_round = next(
                (pr for pr in party_rounds if pr.round_id == prompt_round_id),
                None
            )

            if prompt_party_round:
                result = await self.db.execute(
                    select(QFPlayer)
                    .join(PartyParticipant, QFPlayer.player_id == PartyParticipant.player_id)
                    .where(PartyParticipant.participant_id == prompt_party_round.participant_id)
                )
                prompt_player = result.scalar_one_or_none()
                prompt_username = prompt_player.username if prompt_player else "Unknown"
            else:
                prompt_username = "Unknown"

            # Count votes for each phrase
            result = await self.db.execute(
                select(
                    Vote.voted_phrase,
                    func.count(Vote.vote_id).label('vote_count')
                )
                .where(Vote.phraseset_id == phraseset_id)
                .group_by(Vote.voted_phrase)
            )
            vote_counts = {row[0]: row[1] for row in result.all()}

            # Determine which phrase got most votes
            original_votes = vote_counts.get(ps.original_phrase, 0)
            copy1_votes = vote_counts.get(ps.copy_phrase_1, 0)
            copy2_votes = vote_counts.get(ps.copy_phrase_2, 0)

            max_votes = max(original_votes, copy1_votes, copy2_votes)
            if original_votes == max_votes:
                most_votes = 'original'
            elif copy1_votes == max_votes:
                most_votes = 'copy1'
            else:
                most_votes = 'copy2'

            summaries.append({
                'phraseset_id': str(phraseset_id),
                'prompt_text': ps.prompt_text,
                'original_phrase': ps.original_phrase,
                'vote_count': ps.vote_count,
                'original_player': prompt_username,
                'most_votes': most_votes,
                'votes_breakdown': {
                    'original': original_votes,
                    'copy1': copy1_votes,
                    'copy2': copy2_votes,
                },
            })

        return summaries

    async def get_player_session_stats(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> Dict:
        """Get individual player statistics for this session.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player

        Returns:
            dict: Player's session statistics
        """
        # Calculate full results and extract player stats
        results = await self.calculate_session_results(session_id)

        # Find player in rankings
        player_stats = next(
            (p for p in results['rankings'] if p['player_id'] == str(player_id)),
            None
        )

        if not player_stats:
            raise PartyModeError(f"Player {player_id} not found in session {session_id}")

        # Add awards won by this player
        player_awards = []
        for award_name, award_data in results['awards'].items():
            if award_data['player_id'] == str(player_id):
                player_awards.append({
                    'award': award_name,
                    'metric_value': award_data['metric_value'],
                })

        return {
            **player_stats,
            'awards_won': player_awards,
        }
