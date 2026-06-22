"""Crowdcraft backend package initialization."""

from backend.sqlite import install_sqlite_connection_policy


install_sqlite_connection_policy()
