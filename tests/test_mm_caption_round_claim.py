"""Round ownership regressions for MemeMint caption submissions."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from backend.models.mm.caption import MMCaption
from backend.models.mm.caption_submission import MMCaptionSubmission
from backend.models.mm.image import MMImage
from backend.models.mm.player_daily_state import MMPlayerDailyState
from backend.models.mm.vote_round import MMVoteRound
from backend.schemas.mm_round import RoundDetails
from backend.services.mm.caption_service import MMCaptionService
from backend.services.mm.player_service import MMPlayerService
from backend.services.transaction_service import TransactionService
from backend.utils.model_registry import GameType
from backend.utils.passwords import hash_password


def test_round_details_preserves_submitted_caption_fields():
    caption_id = uuid.uuid4()
    details = RoundDetails(
        round_id=uuid.uuid4(),
        type="vote",
        status="captioned",
        image_id=uuid.uuid4(),
        image_url="https://example.com/image.jpg",
        cost=5,
        submitted_caption_id=caption_id,
        submitted_caption_text="A submitted caption",
    )

    payload = details.model_dump()
    assert payload["submitted_caption_id"] == caption_id
    assert payload["submitted_caption_text"] == "A submitted caption"


@pytest.mark.asyncio
async def test_caption_submission_claims_vote_round_once(db_session):
    suffix = uuid.uuid4().hex[:8]
    player = await MMPlayerService(db_session).create_player(
        username=f"mm_caption_{suffix}",
        email=f"mm_caption_{suffix}@example.com",
        password_hash=hash_password("TestPassword123!"),
    )
    player_id = player.player_id
    image = MMImage(
        source_url="https://example.com/mm-round.jpg",
        thumbnail_url="https://example.com/mm-round-thumb.jpg",
        tags=["test"],
    )
    shown = MMCaption(
        image=image,
        author_player_id=None,
        kind="original",
        text="Existing caption",
        status="active",
        shows=0,
        picks=0,
    )
    db_session.add_all([image, shown])
    await db_session.flush()
    round_obj = MMVoteRound(
        player_id=player.player_id,
        image_id=image.image_id,
        caption_ids_shown=[str(shown.caption_id)],
        chosen_caption_id=shown.caption_id,
        entry_cost=5,
    )
    db_session.add(round_obj)
    await db_session.commit()

    service = MMCaptionService(db_session)
    service._detect_riff_or_original = AsyncMock(return_value=("original", None))
    transactions = TransactionService(db_session, GameType.MM)

    result = await service.submit_caption(
        player,
        round_obj,
        "A new caption",
        [shown],
        transactions,
    )
    assert result["used_free_slot"] is True

    with pytest.raises(ValueError, match="caption_already_submitted_for_round"):
        await service.submit_caption(
            player,
            round_obj,
            "A second caption",
            [shown],
            transactions,
        )

    assert await db_session.scalar(
        select(func.count(MMCaptionSubmission.submission_id))
    ) == 1
    assert await db_session.scalar(
        select(MMPlayerDailyState.free_captions_used).where(
            MMPlayerDailyState.player_id == player_id
        )
    ) == 1
