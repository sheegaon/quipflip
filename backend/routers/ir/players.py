"""Player-focused endpoints for Initial Reaction (IR)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.ir.enums import IRSetStatus
from backend.models.ir.ir_backronym_entry import IRBackronymEntry
from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.ir_player import IRPlayer
from backend.routers.ir.dependencies import get_ir_current_player
from backend.routers.ir.schemas import (
    IRClaimDailyBonusResponse,
    IRDashboardActiveSession,
    IRDashboardPlayerSummary,
    IRDashboardResponse,
    IRPendingResult,
    IRPlayerBalanceResponse,
    IRPlayerResponse,
)
from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
from backend.services.ir.ir_daily_bonus_service import IRDailyBonusError, IRDailyBonusService
from backend.services.ir.ir_result_view_service import IRResultViewService
from backend.services.ir.player_service import IRPlayerService

router = APIRouter()


@router.get("/me", response_model=IRPlayerResponse)
async def get_current_player(
    player: IRPlayer = Depends(get_ir_current_player),
) -> IRPlayerResponse:
    """Get current authenticated player information."""
    return IRPlayerResponse(
        player_id=str(player.player_id),
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )


@router.get("/player/balance", response_model=IRPlayerBalanceResponse)
async def get_player_balance(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRPlayerBalanceResponse:
    """Return wallet/vault balances and bonus availability."""

    player_service = IRPlayerService(db)
    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    if not fresh_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    bonus_service = IRDailyBonusService(db)
    bonus_available = await bonus_service.is_bonus_available(str(player.player_id))

    return IRPlayerBalanceResponse(
        wallet=fresh_player.wallet,
        vault=fresh_player.vault,
        daily_bonus_available=bonus_available,
    )


@router.get("/player/dashboard", response_model=IRDashboardResponse)
async def get_player_dashboard(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRDashboardResponse:
    """Return dashboard summary for the signed-in player."""

    player_service = IRPlayerService(db)
    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    if not fresh_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    bonus_service = IRDailyBonusService(db)
    bonus_available = await bonus_service.is_bonus_available(str(player.player_id))

    active_stmt = (
        select(IRBackronymSet)
        .join(IRBackronymEntry, IRBackronymEntry.set_id == IRBackronymSet.set_id)
        .where(IRBackronymEntry.player_id == str(player.player_id))
        .where(
            IRBackronymSet.status.in_([IRSetStatus.OPEN, IRSetStatus.VOTING])
        )
        .order_by(IRBackronymSet.created_at.desc())
        .limit(1)
    )
    active_result = await db.execute(active_stmt)
    active_set = active_result.scalars().first()

    result_service = IRResultViewService(db)
    pending = await result_service.get_pending_results(str(player.player_id))
    pending_models = [IRPendingResult(**item) for item in pending]

    active_session = None
    if active_set:
        set_service = IRBackronymSetService(db)
        set_details = await set_service.get_set_details(str(active_set.set_id))

        has_submitted_entry = False
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    has_submitted_entry = True
                    break

        has_voted = False
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    has_voted = True
                    break

        active_session = IRDashboardActiveSession(
            set_id=str(active_set.set_id),
            word=active_set.word,
            status=str(active_set.status),
            has_submitted_entry=has_submitted_entry,
            has_voted=has_voted,
        )

    return IRDashboardResponse(
        player=IRDashboardPlayerSummary(
            player_id=str(fresh_player.player_id),
            username=fresh_player.username,
            wallet=fresh_player.wallet,
            vault=fresh_player.vault,
            daily_bonus_available=bonus_available,
            created_at=fresh_player.created_at,
        ),
        active_session=active_session,
        pending_results=pending_models,
        wallet=fresh_player.wallet,
        vault=fresh_player.vault,
        daily_bonus_available=bonus_available,
    )


@router.post("/player/claim-daily-bonus", response_model=IRClaimDailyBonusResponse)
async def claim_daily_bonus(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRClaimDailyBonusResponse:
    """Claim the daily InitCoin bonus."""

    bonus_service = IRDailyBonusService(db)
    player_service = IRPlayerService(db)

    try:
        bonus = await bonus_service.claim_bonus(str(player.player_id))
    except IRDailyBonusError as exc:
        status = 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    refreshed_player = await player_service.get_player_by_id(str(player.player_id))
    if not refreshed_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    claimed_at = bonus["claimed_at"]
    if isinstance(claimed_at, str):
        claimed_at = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
    next_claim = claimed_at + timedelta(hours=24)

    return IRClaimDailyBonusResponse(
        bonus_amount=bonus["amount"],
        new_balance=refreshed_player.wallet,
        next_claim_available_at=next_claim.isoformat(),
    )


@router.get("/players/{player_id}", response_model=IRPlayerResponse)
async def get_player(
    player_id: str,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_ir_current_player),
) -> IRPlayerResponse:
    """Get IR player information by ID."""

    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return IRPlayerResponse(
        player_id=str(player.player_id),
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )
