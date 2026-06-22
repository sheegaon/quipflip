"""Helpers for stable idempotency key generation."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
import json
from hashlib import sha256
from uuid import UUID

_EXCLUDED_FIELDS = {
    "transaction_id",
    "created_at",
    "updated_at",
    "version",
    "idempotency_key",
    "wallet_balance_after",
    "vault_balance_after",
    "balance_after",
}


def _normalize_value(value):
    """Normalize values for stable hashing."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value.hex
    if isinstance(value, str):
        try:
            return UUID(value).hex
        except ValueError:
            pass
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted([_normalize_value(item) for item in value], key=lambda item: str(item))
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    return value


def build_idempotency_key(namespace: str, values: Mapping[str, object]) -> str:
    """Build a stable idempotency key from the supplied values."""
    normalized = {
        str(key): _normalize_value(value)
        for key, value in sorted(values.items(), key=lambda pair: str(pair[0]))
        if key not in _EXCLUDED_FIELDS and value is not None
    }
    payload = json.dumps(
        {"namespace": namespace, "values": normalized},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()