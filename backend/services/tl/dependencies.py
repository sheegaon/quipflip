"""Dependency providers for ThinkLink services."""

from functools import lru_cache
from backend.services.tl.matching_service import TLMatchingService
from backend.services.tl.clustering_service import TLClusteringService
from backend.services.tl.scoring_service import TLScoringService
from backend.services.tl.prompt_service import TLPromptService
from backend.services.tl.round_service import TLRoundService


@lru_cache()
def get_matching_service() -> TLMatchingService:
    """Provide a singleton MatchingService instance."""

    return TLMatchingService()


@lru_cache()
def get_scoring_service() -> TLScoringService:
    """Provide a singleton ScoringService instance."""

    return TLScoringService()


@lru_cache()
def get_prompt_service() -> TLPromptService:
    """Provide a singleton PromptService instance."""

    return TLPromptService(get_matching_service())


@lru_cache()
def get_clustering_service() -> TLClusteringService:
    """Provide a singleton ClusteringService instance."""

    return TLClusteringService(get_matching_service())


@lru_cache()
def get_round_service() -> TLRoundService:
    """Provide a singleton RoundService instance."""

    return TLRoundService(
        matching_service=get_matching_service(),
        clustering_service=get_clustering_service(),
        scoring_service=get_scoring_service(),
        prompt_service=get_prompt_service(),
    )

