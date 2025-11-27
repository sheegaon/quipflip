"""Unit tests for the Meme Mint vote service."""
import uuid

import pytest
from sqlalchemy import select

from backend.models.mm.caption import MMCaption
from backend.models.mm.player import MMPlayer
from backend.models.mm.image import MMImage
from backend.models.mm.vote_round import MMVoteRound
from backend.models.mm.transaction import MMTransaction
from backend.services.mm.vote_service import MMVoteService
from backend.services.transaction_service import TransactionService
from backend.utils.model_registry import GameType


@pytest.fixture
async def mm_vote_context(db_session):
    """Create Meme Mint players, caption, and helper for vote rounds."""
    unique_id = uuid.uuid4().hex[:8]

    voter = MMPlayer(
        username=f"mm_voter_{unique_id}",
        username_canonical=f"mm_voter_{unique_id}",
        email=f"mm_voter_{unique_id}@example.com",
        password_hash="hash",
        wallet=1000,
        vault=0,
    )
    author = MMPlayer(
        username=f"mm_author_{unique_id}",
        username_canonical=f"mm_author_{unique_id}",
        email=f"mm_author_{unique_id}@example.com",
        password_hash="hash",
        wallet=1000,
        vault=0,
    )
    image = MMImage(
        source_url="https://example.com/image.jpg",
        thumbnail_url="https://example.com/thumb.jpg",
        tags=["test"],
    )
    caption = MMCaption(
        image=image,
        author=author,
        kind="original",
        text="Test caption",
        shows=0,
        picks=0,
    )

    db_session.add_all([voter, author, image, caption])
    await db_session.commit()

    async def create_round(entry_cost: int = 0) -> MMVoteRound:
        round_obj = MMVoteRound(
            player_id=voter.player_id,
            image_id=image.image_id,
            caption_ids_shown=[str(caption.caption_id)],
            entry_cost=entry_cost,
        )
        db_session.add(round_obj)
        await db_session.commit()
        await db_session.refresh(round_obj)
        return round_obj

    return {
        "voter": voter,
        "author": author,
        "image": image,
        "caption": caption,
        "create_round": create_round,
    }


@pytest.mark.asyncio
async def test_first_vote_bonus_awards_default_amount(db_session, mm_vote_context):
    round_obj = await mm_vote_context["create_round"]()
    vote_service = MMVoteService(db_session)
    transaction_service = TransactionService(db_session, GameType.MM)

    voter = mm_vote_context["voter"]
    caption = mm_vote_context["caption"]
    starting_wallet = voter.wallet

    result = await vote_service.submit_vote(
        round_obj,
        caption.caption_id,
        voter,
        transaction_service,
    )

    await db_session.refresh(voter)
    await db_session.refresh(caption)

    assert result["first_vote_bonus"] is True
    assert voter.wallet == starting_wallet + 2
    assert caption.first_vote_awarded is True

    bonus_transactions = await db_session.execute(
        select(MMTransaction).where(
            MMTransaction.type == "mm_first_vote_bonus",
            MMTransaction.player_id == voter.player_id,
        )
    )
    assert len(bonus_transactions.scalars().all()) == 1


@pytest.mark.asyncio
async def test_first_vote_bonus_only_applied_once(db_session, mm_vote_context):
    vote_service = MMVoteService(db_session)
    transaction_service = TransactionService(db_session, GameType.MM)

    voter = mm_vote_context["voter"]
    caption = mm_vote_context["caption"]

    first_round = await mm_vote_context["create_round"]()
    await vote_service.submit_vote(first_round, caption.caption_id, voter, transaction_service)
    await db_session.refresh(voter)
    starting_wallet_after_first = voter.wallet

    second_round = await mm_vote_context["create_round"]()
    result = await vote_service.submit_vote(
        second_round,
        caption.caption_id,
        voter,
        transaction_service,
    )

    await db_session.refresh(voter)

    assert result["first_vote_bonus"] is False
    assert voter.wallet == starting_wallet_after_first

    bonus_transactions = await db_session.execute(
        select(MMTransaction).where(
            MMTransaction.type == "mm_first_vote_bonus",
            MMTransaction.player_id == voter.player_id,
        )
    )
    assert len(bonus_transactions.scalars().all()) == 1
