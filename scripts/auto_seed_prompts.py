#!/usr/bin/env python3
"""Auto-seed prompts if database is empty (non-interactive)."""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import sync_prompts_with_database

if __name__ == "__main__":
    asyncio.run(sync_prompts_with_database())
