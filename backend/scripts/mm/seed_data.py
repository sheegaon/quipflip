"""Seed Meme Mint data with test images and captions."""

import asyncio
import logging
from pathlib import Path
from datetime import datetime, UTC
from uuid import uuid4, UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.config import get_settings
from backend.models.mm.image import MMImage
from backend.models.mm.caption import MMCaption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Special UUID for system/seeded content - this will be consistent across all environments
SYSTEM_PLAYER_ID = UUID("00000000-0000-0000-0000-000000000001")


IMAGES_DIR = Path(__file__).parent / "mm_images"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


# Generic captions that can work with any image
GENERIC_CAPTIONS = [
    "When you finally understand the assignment",
    "Me pretending to be productive",
    "That moment when everything clicks",
    "Monday mood",
    "Living my best life",
    "This is fine",
    "Big mood energy",
    "Plot twist: it gets worse",
    "My therapist needs to see this",
    "Nobody asked but here we are",
    "The accuracy is unsettling",
    "We've all been here",
    "Why is this so relatable",
    "This hits different",
    "I felt that",
    "Every single time",
    "Tell me I'm wrong",
    "This is the way",
    "Outstanding move",
    "Well yes, but actually no",
    "I see this as an absolute win",
    "Professionals have standards",
    "Sometimes genius is... it's almost frightening",
    "Carefully, he's a hero",
    "Because that's what heroes do",
    "I don't think the system works",
    "So uncivilized",
    "You get what you deserve",
    "Reality is often disappointing",
    "I'm something of a scientist myself",
]


def build_placeholder_images() -> list[dict]:
    """Create placeholder image records from the local mm_images directory.

    Only uses local images - no fallback to remote placeholders.
    """

    if not IMAGES_DIR.exists():
        raise FileNotFoundError(
            f"Local image directory not found at {IMAGES_DIR}. "
            "Please ensure backend/data/mm_images/ exists with image files."
        )

    placeholder_images = []

    for path in sorted(IMAGES_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        placeholder_images.append({
            "source_url": f"/api/mm/images/{path.name}",
            "thumbnail_url": None,
            "attribution_text": f"Image {path.stem}",
            "tags": [],
        })

    if not placeholder_images:
        raise FileNotFoundError(
            f"No valid image files found in {IMAGES_DIR}. "
            f"Supported formats: {', '.join(IMAGE_EXTENSIONS)}"
        )

    return placeholder_images


async def seed_data(db: AsyncSession):
    """Seed the database with test images and captions."""

    # Check if data already exists
    stmt = select(MMImage).limit(1)
    result = await db.execute(stmt)
    existing_images = result.scalar_one_or_none()

    if existing_images:
        logger.info("Images already exist, checking if we need more captions...")
    else:
        logger.info("No existing images, creating seed data...")

    # Create or get images
    image_ids = []
    for img_data in build_placeholder_images():
        # Check if image already exists by source_url
        stmt = select(MMImage).where(MMImage.source_url == img_data["source_url"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Image already exists: {img_data['source_url']}")
            image_ids.append(existing.image_id)
            continue

        image = MMImage(
            image_id=uuid4(),
            source_url=img_data["source_url"],
            thumbnail_url=img_data["thumbnail_url"],
            attribution_text=img_data["attribution_text"],
            tags=img_data["tags"],
            status="active",
            created_at=datetime.now(UTC),
            created_by_player_id=None,  # System-generated
        )
        db.add(image)
        image_ids.append(image.image_id)
        logger.info(f"Created image: {img_data['source_url']}")

    await db.flush()

    # Create captions for each image
    caption_count = 0
    for image_id in image_ids:
        # Check how many captions this image already has
        stmt = select(MMCaption).where(MMCaption.image_id == image_id)
        result = await db.execute(stmt)
        existing_captions = len(list(result.scalars().all()))

        if existing_captions >= 10:
            logger.info(f"Image {image_id} already has {existing_captions} captions, skipping")
            continue

        # Determine how many captions to add
        captions_needed = max(10 - existing_captions, 0)

        # Create captions for this image
        for i in range(captions_needed):
            if i >= len(GENERIC_CAPTIONS):
                break

            caption = MMCaption(
                caption_id=uuid4(),
                image_id=image_id,
                author_player_id=SYSTEM_PLAYER_ID,  # System/AI-generated caption
                kind="original",
                parent_caption_id=None,
                text=GENERIC_CAPTIONS[(caption_count + i) % len(GENERIC_CAPTIONS)],
                status="active",
                created_at=datetime.now(UTC),
                shows=0,
                picks=0,
                first_vote_awarded=False,
                quality_score=0.25,  # Initial quality score (1/4)
                lifetime_earnings_gross=0,
                lifetime_to_wallet=0,
                lifetime_to_vault=0,
            )
            db.add(caption)
            caption_count += 1

        logger.info(f"Created {captions_needed} captions for image {image_id}")

    await db.commit()
    logger.info(f"Seed data complete: {len(image_ids)} images, {caption_count} new captions")


async def main():
    """Main entry point."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed_data(session)

    await engine.dispose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
