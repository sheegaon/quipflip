"""Dependency providers for ThinkLink services."""

from functools import lru_cache
from backend.services.tl.matching_service import MatchingService
from backend.services.tl.clustering_service import ClusteringService
from backend.services.tl.scoring_service import ScoringService
from backend.services.tl.prompt_service import PromptService
from backend.services.tl.round_service import RoundService


@lru_cache()
def get_matching_service() -> MatchingService:
    """Provide a singleton MatchingService instance."""

    return MatchingService()


@lru_cache()
def get_scoring_service() -> ScoringService:
    """Provide a singleton ScoringService instance."""

    return ScoringService()


@lru_cache()
def get_prompt_service() -> PromptService:
    """Provide a singleton PromptService instance."""

    return PromptService(get_matching_service())


@lru_cache()
def get_clustering_service() -> ClusteringService:
    """Provide a singleton ClusteringService instance."""

    return ClusteringService(get_matching_service())


@lru_cache()
def get_round_service() -> RoundService:
    """Provide a singleton RoundService instance."""

    return RoundService(
        matching_service=get_matching_service(),
        clustering_service=get_clustering_service(),
        scoring_service=get_scoring_service(),
        prompt_service=get_prompt_service(),
    )

