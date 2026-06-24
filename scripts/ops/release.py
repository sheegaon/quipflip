"""Release and content-sync operations for Crowdcraft."""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from backend.runtime.config import resolve_runtime_paths, validate_runtime_resources, validate_runtime_settings


def validate_config() -> dict[str, Any]:
    from backend.config import get_settings

    errors: list[str] = []
    paths_payload: dict[str, Any] = {}
    try:
        settings = get_settings()
        paths = resolve_runtime_paths(settings)
        paths_payload = {key: str(value) if isinstance(value, Path) else value for key, value in asdict(paths).items()}
        errors.extend(validate_runtime_settings(settings))
        errors.extend(validate_runtime_resources(settings))
    except Exception as exc:
        errors.append(f"configuration validation failed: {exc}")

    tool_checks = {
        "git": shutil.which("git") is not None,
        "python": shutil.which("python3") is not None or shutil.which("python") is not None,
        "npm": shutil.which("npm") is not None,
        "cloudflared": shutil.which("cloudflared") is not None,
        "launchctl": shutil.which("launchctl") is not None,
    }

    return {
        "ok": not errors,
        "errors": errors,
        "paths": paths_payload,
        "tool_checks": tool_checks,
    }


async def snapshot_content_state() -> dict[str, Any]:
    from backend.database import AsyncSessionLocal
    from backend.models.mm.caption import MMCaption
    from backend.models.mm.image import MMImage
    from backend.models.player import Player
    from backend.models.qf.prompt import Prompt
    from backend.models.qf.quest import QFQuest
    from backend.models.tl import TLAnswer, TLPrompt
    from backend.scripts.mm.import_images import SEED_CAPTIONS, find_image_files
    from backend.scripts.tl.seed_answers import load_completions_from_csv
    from backend.scripts.tl.seed_prompts import load_prompts_from_csv as load_tl_prompts
    from backend.services.qf.prompt_seeder import load_prompts_from_csv as load_qf_prompts
    from backend.services.qf.quest_service import QuestService

    qf_prompts_source = len(load_qf_prompts())
    tl_prompts_source = len(load_tl_prompts())
    tl_answers_source = sum(len(completions) for completions in load_completions_from_csv().values())
    image_files = find_image_files()
    mm_images_source = len(image_files)
    mm_captions_source = len(SEED_CAPTIONS) * mm_images_source
    starter_quest_types = {quest_type.value for quest_type in QuestService.STARTER_QUEST_TYPES}

    async with AsyncSessionLocal() as db:
        counts = {
            "players": await db.scalar(select(func.count(Player.player_id))),
            "qf_prompts": await db.scalar(select(func.count(Prompt.prompt_id))),
            "qf_quests": await db.scalar(
                select(func.count(QFQuest.quest_id)).where(QFQuest.quest_type.in_(starter_quest_types))
            ),
            "mm_images": await db.scalar(select(func.count(MMImage.image_id))),
            "mm_captions": await db.scalar(select(func.count(MMCaption.caption_id))),
            "tl_prompts": await db.scalar(select(func.count(TLPrompt.prompt_id))),
            "tl_answers": await db.scalar(select(func.count(TLAnswer.answer_id))),
        }

    return {
        "source": {
            "qf_prompts": qf_prompts_source,
            "mm_images": mm_images_source,
            "mm_captions": mm_captions_source,
            "tl_prompts": tl_prompts_source,
            "tl_answers": tl_answers_source,
        },
        "database": counts,
    }


async def sync_content(*, apply: bool, release_id: str) -> dict[str, Any]:
    report = await snapshot_content_state()
    report["release_id"] = release_id
    report["applied"] = apply
    if apply:
        from backend.main import run_release_sync_content

        await run_release_sync_content()
        report["applied"] = True
    return report


def cleanup_retention(*, apply: bool, command_id: str) -> dict[str, Any]:
    paths = get_deployment_paths()
    backup_root = paths.runtime_root / "backups"
    backup_dirs = sorted(
        [path for path in backup_root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if backup_root.exists() else []

    return {
        "command_id": command_id,
        "apply": apply,
        "backup_root": str(backup_root),
        "backup_count": len(backup_dirs),
        "backups": [str(path) for path in backup_dirs],
        "deleted": [],
        "note": "Retention policy is not yet encoded; this command currently reports backup inventory only.",
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_sync_content(apply: bool, release_id: str) -> dict[str, Any]:
    return asyncio.run(sync_content(apply=apply, release_id=release_id))
