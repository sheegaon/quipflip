"""Utility functions for phraseset operations."""
import logging
from backend.models.qf.phraseset import Phraseset

logger = logging.getLogger(__name__)


def validate_phraseset_contributor_rounds(phraseset: Phraseset) -> None:
    """
    Validate that all contributor round IDs are present in a phraseset.

    Raises ValueError if any round IDs are NULL.
    """
    missing_ids = []
    if phraseset.prompt_round_id is None:
        missing_ids.append("prompt(NULL)")
    if phraseset.copy_round_1_id is None:
        missing_ids.append("copy1(NULL)")
    if phraseset.copy_round_2_id is None:
        missing_ids.append("copy2(NULL)")

    if missing_ids:
        logger.error(
            f"Phraseset {phraseset.phraseset_id} has NULL round IDs: {', '.join(missing_ids)}. "
            f"Status: {phraseset.status}. This is a data integrity issue."
        )
        raise ValueError(f"Phraseset has missing contributor rounds: {', '.join(missing_ids)}")
