"""Service utilities for generating and validating usernames."""

from __future__ import annotations

import random
from itertools import count
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.username_pool import USERNAME_POOL
from backend.data.profanity_list import contains_profanity
from backend.models.player import Player


def canonicalize_username(username: str) -> str:
    """Convert a username into its canonical lowercase alphanumeric form."""
    return "".join(ch for ch in username.lower() if ch.isalnum())


def normalize_username(username: str) -> str:
    """Normalize whitespace for display."""
    return " ".join(username.strip().split())


def is_username_input_valid(username: str) -> bool:
    """Validate that the input contains only basic alphanumerics and spaces."""
    stripped = username.strip()
    if not stripped:
        return False
    return all(ch.isalnum() or ch.isspace() for ch in stripped)


def is_username_profanity_free(username: str) -> bool:
    """Validate that the username does not contain profanity."""
    if not username.strip():
        return True
    return not contains_profanity(username)


class UsernameService:
    """Encapsulates username generation and lookup helpers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _existing_canonicals(self) -> set[str]:
        result = await self.db.execute(select(Player.username_canonical))
        return {row[0] for row in result if row[0]}

    async def generate_unique_username(self) -> Tuple[str, str]:
        """Generate a unique (display, canonical) username pair."""
        taken = await self._existing_canonicals()
        pool = USERNAME_POOL.copy()

        # Group by length and shuffle within each group
        length_groups = {}
        for username in pool:
            length = 0 if len(username) < 15 else len(username)
            if length not in length_groups:
                length_groups[length] = []
            length_groups[length].append(username)

        # Shuffle each length group and combine in order
        pool = []
        for length in sorted(length_groups.keys()):
            group = length_groups[length]
            random.shuffle(group)
            pool.extend(group)

        normalized_pool: list[tuple[str, str]] = []
        for candidate in pool:
            display = normalize_username(candidate)
            canonical = canonicalize_username(display)
            if not canonical:
                continue
            normalized_pool.append((display, canonical))
            if canonical not in taken:
                taken.add(canonical)
                return display, canonical

        # Exhausted base pool, fall back to numeric suffixes by iterating suffixes first.
        for suffix in count(2):
            for base_display, _ in normalized_pool:
                display = f"{base_display} {suffix}"
                canonical = canonicalize_username(display)
                if canonical and canonical not in taken:
                    taken.add(canonical)
                    return display, canonical

        raise RuntimeError("Unable to generate a unique username.")

    async def find_player_by_username(self, username: str) -> Player | None:
        """Return the player matching the supplied username (case-insensitive)."""
        if not username:
            return None
        canonical = canonicalize_username(username)
        if not canonical:
            return None
        result = await self.db.execute(
            select(Player).where(Player.username_canonical == canonical)
        )
        return result.scalar_one_or_none()
