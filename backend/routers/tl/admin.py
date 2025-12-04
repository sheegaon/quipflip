"""ThinkLink (TL) admin API router - prompt seeding, corpus management."""
import logging
from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.schemas.base import BaseSchema
from backend.services import GameType
from backend.services.tl.prompt_service import TLPromptService
from backend.services.tl.clustering_service import (
    TLClusteringService,
    prune_corpus as service_prune_corpus,
)
from backend.services.tl.matching_service import TLMatchingService
from backend.services.tl.scoring_service import TLScoringService
from backend.models.tl import TLPrompt, TLAnswer, TLCluster
from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_admin_player(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> Player:
    """Get current player authenticated for ThinkLink and verify admin status."""
    player = await get_current_player(
        request=request,
        game_type=GameType.TL,
        authorization=authorization,
        db=db,
    )
    if not player.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return player


class SeedPromptsRequest(BaseModel):
    """Request to seed prompts."""
    prompts: List[str] = []  # List of prompt texts


class SeedPromptsResponse(BaseSchema):
    """Response from seeding prompts."""
    created_count: int
    skipped_count: int
    total_count: int


class CorpusStats(BaseSchema):
    """Statistics for a prompt's answer corpus."""
    prompt_id: UUID
    prompt_text: str
    active_answer_count: int
    cluster_count: int
    total_weight: float
    largest_cluster_size: int
    smallest_cluster_size: int


class PruneCorpusResponse(BaseSchema):
    """Response from corpus pruning."""
    prompt_id: UUID
    removed_count: int
    current_active_count: int
    target_count: int


@router.post("/prompts/seed", response_model=SeedPromptsResponse)
async def seed_prompts(
    request_body: SeedPromptsRequest,
    player: Player = Depends(get_admin_player),
    db: AsyncSession = Depends(get_db),
):
    """Seed ThinkLink prompts from a list.

    Admin only. Each prompt will be embedded and marked as active.
    """
    try:
        if not request_body.prompts:
            raise HTTPException(
                status_code=400, detail="prompts list cannot be empty"
            )

        logger.info(f"🌱 Seeding {len(request_body.prompts)} prompts...")

        # Initialize services
        matching_service = TLMatchingService()
        prompt_service = TLPromptService(matching_service)

        # Seed prompts
        created, skipped = await prompt_service.seed_prompts_from_list(
            db, request_body.prompts
        )

        # Commit changes
        await db.commit()

        logger.info(f"✅ Prompts seeded: {created} created, {skipped} skipped")

        return SeedPromptsResponse(
            created_count=created,
            skipped_count=skipped,
            total_count=created + skipped,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error seeding prompts: {e}")
        raise HTTPException(status_code=500, detail="seed_failed")


@router.get("/corpus/{prompt_id}", response_model=CorpusStats)
async def get_corpus_stats(
    prompt_id: UUID = Path(..., description="Prompt ID"),
    player: Player = Depends(get_admin_player),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a prompt's answer corpus.

    Admin only. Shows active answer count, cluster distribution, etc.
    """
    from sqlalchemy.orm import load_only

    try:
        # Get prompt (use load_only to avoid pgvector deserialization issue)
        result = await db.execute(
            select(TLPrompt)
            .options(load_only(TLPrompt.prompt_id, TLPrompt.text, TLPrompt.is_active))
            .where(TLPrompt.prompt_id == prompt_id)
        )
        prompt = result.scalars().first()
        if not prompt:
            raise HTTPException(status_code=404, detail="prompt_not_found")

        # Count active answers
        result = await db.execute(
            select(TLAnswer).where(
                (TLAnswer.prompt_id == prompt_id) & (TLAnswer.is_active == True)
            )
        )
        answers = result.scalars().all()
        active_answer_count = len(answers)

        # Get clusters
        result = await db.execute(
            select(TLCluster).where(TLCluster.prompt_id == prompt_id)
        )
        clusters = result.scalars().all()
        cluster_count = len(clusters)

        # Calculate stats
        cluster_sizes = [c.size for c in clusters]
        largest_cluster_size = max(cluster_sizes) if cluster_sizes else 0
        smallest_cluster_size = min(cluster_sizes) if cluster_sizes else 0

        # Calculate total weight (single efficient query instead of N+1)
        cluster_ids = [str(c.cluster_id) for c in clusters]
        scoring_service = TLScoringService()
        total_weight = await scoring_service._calculate_total_weight(db, cluster_ids)

        logger.info(
            f"📊 Corpus stats for {prompt_id}: "
            f"{active_answer_count} answers, {cluster_count} clusters, weight={total_weight:.2f}"
        )

        return CorpusStats(
            prompt_id=prompt_id,
            prompt_text=prompt.text,
            active_answer_count=active_answer_count,
            cluster_count=cluster_count,
            total_weight=total_weight,
            largest_cluster_size=largest_cluster_size,
            smallest_cluster_size=smallest_cluster_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching corpus stats: {e}")
        raise HTTPException(status_code=500, detail="stats_failed")


@router.post("/corpus/{prompt_id}/prune", response_model=PruneCorpusResponse)
async def prune_corpus(
    prompt_id: UUID = Path(..., description="Prompt ID"),
    player: Player = Depends(get_admin_player),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger corpus pruning for a prompt.

    Admin only. Prunes to K=1000 active answers per prompt by removing
    lowest-usefulness answers.
    """
    try:
        settings = get_settings()
        keep_count = settings.tl_active_corpus_cap

        logger.debug(f"🔪 Pruning corpus for {prompt_id}...")

        # Initialize services
        matching_service = TLMatchingService()
        clustering_service = TLClusteringService(matching_service)

        # Prune corpus
        removed_count, current_count = await service_prune_corpus(
            db, str(prompt_id), keep_count=keep_count
        )

        # Commit changes
        await db.commit()

        logger.debug(f"✅ Corpus pruned: removed {removed_count}, {current_count} active")

        return PruneCorpusResponse(
            prompt_id=prompt_id,
            removed_count=removed_count,
            current_active_count=current_count,
            target_count=keep_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error pruning corpus: {e}")
        raise HTTPException(status_code=500, detail="prune_failed")
