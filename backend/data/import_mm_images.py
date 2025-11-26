"""Import images from backend/data/mm_images and seed captions from CSV.

This script:
1. Scans backend/data/mm_images/ for image files (jpg, jpeg, png, gif, webp)
2. Creates MMImage records for each new image
3. Reads seed captions from mm_seed_captions.csv
4. Creates MMCaption records for seed captions

Usage:
    PYTHONPATH=/path/to/quipflip python backend/data/import_mm_images.py
"""

import asyncio
import csv
import logging
import os
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.config import get_settings
from backend.models.mm.image import MMImage
from backend.models.mm.caption import MMCaption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Paths
IMAGES_DIR = Path(__file__).parent / 'mm_images'
CAPTIONS_CSV = Path(__file__).parent / 'mm_seed_captions.csv'


def load_seed_captions() -> dict[str, list[str]]:
    """Load seed captions from CSV file.

    Returns:
        Dictionary mapping image filename to list of seed captions
    """
    captions_map = {}

    if not CAPTIONS_CSV.exists():
        logger.warning(f"Captions CSV not found: {CAPTIONS_CSV}")
        return captions_map

    with open(CAPTIONS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_file = row['image_file']
            # Collect all seed_caption columns
            captions = []
            for i in range(1, 100):  # Support up to 99 captions
                col_name = f'seed_caption{i}'
                if col_name in row and row[col_name]:
                    captions.append(row[col_name])
                else:
                    break

            if captions:
                captions_map[image_file] = captions
                logger.info(f"Loaded {len(captions)} seed captions for {image_file}")

    return captions_map


def find_image_files() -> list[Path]:
    """Find all image files in the mm_images directory.

    Returns:
        List of Path objects for image files
    """
    if not IMAGES_DIR.exists():
        logger.error(f"Images directory not found: {IMAGES_DIR}")
        return []

    image_files = []
    for file_path in IMAGES_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            image_files.append(file_path)

    logger.info(f"Found {len(image_files)} image files in {IMAGES_DIR}")
    return image_files


async def import_images(db: AsyncSession):
    """Import images and seed captions into the database.

    Args:
        db: Database session
    """
    # Load seed captions
    seed_captions = load_seed_captions()

    # Find image files
    image_files = find_image_files()

    if not image_files:
        logger.warning("No image files found to import")
        return

    # Process each image
    images_created = 0
    captions_created = 0

    for image_path in image_files:
        filename = image_path.name

        # Construct URL path (served by FastAPI)
        source_url = f"/api/mm/images/{filename}"

        # Check if image already exists
        stmt = select(MMImage).where(MMImage.source_url == source_url)
        result = await db.execute(stmt)
        existing_image = result.scalar_one_or_none()

        if existing_image:
            logger.info(f"Image already exists: {filename}")
            image_id = existing_image.image_id
        else:
            # Create new image record
            image = MMImage(
                image_id=uuid4(),
                source_url=source_url,
                thumbnail_url=None,  # No thumbnails for now
                attribution_text=f"Image: {filename}",
                tags=[],
                status="active",
                created_at=datetime.now(UTC),
                created_by_player_id=None,  # System-generated
            )
            db.add(image)
            await db.flush([image])
            image_id = image.image_id
            images_created += 1
            logger.info(f"Created image: {filename} (ID: {image_id})")

        # Add seed captions if available
        if filename in seed_captions:
            # Check existing captions for this image
            stmt = select(MMCaption).where(MMCaption.image_id == image_id)
            result = await db.execute(stmt)
            existing_caption_texts = {c.text for c in result.scalars().all()}

            for caption_text in seed_captions[filename]:
                # Skip if caption already exists
                if caption_text in existing_caption_texts:
                    logger.debug(f"Caption already exists for {filename}: {caption_text[:50]}...")
                    continue

                # Create caption
                caption = MMCaption(
                    caption_id=uuid4(),
                    image_id=image_id,
                    author_player_id=None,  # System/seed caption
                    kind="original",
                    parent_caption_id=None,
                    text=caption_text,
                    status="active",
                    created_at=datetime.now(UTC),
                    shows=0,
                    picks=0,
                    first_vote_awarded=False,
                    quality_score=0.25,  # Initial score: (0+1)/(0+3) = 0.333... we'll use 0.25
                    lifetime_earnings_gross=0,
                    lifetime_to_wallet=0,
                    lifetime_to_vault=0,
                )
                db.add(caption)
                captions_created += 1
                logger.debug(f"Created caption for {filename}: {caption_text[:50]}...")

            await db.flush()
            logger.info(f"Added {captions_created} captions for {filename}")

    # Commit all changes
    await db.commit()

    logger.info(f"""
Import complete:
  - Images created: {images_created}
  - Captions created: {captions_created}
  - Total images in directory: {len(image_files)}
    """)


async def main():
    """Main entry point."""
    logger.info("Starting MM image import...")

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await import_images(session)

    await engine.dispose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
