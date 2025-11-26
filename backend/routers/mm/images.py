"""Image serving router for Meme Mint."""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to images directory
IMAGES_DIR = Path(__file__).parent.parent.parent / "data" / "mm_images"


@router.get("/images/{filename}")
async def get_image(filename: str):
    """Serve an image file from the mm_images directory.

    Args:
        filename: Image filename (e.g., "image1.jpeg")

    Returns:
        FileResponse with the image

    Raises:
        HTTPException: 404 if image not found
    """
    # Security: prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    image_path = IMAGES_DIR / filename

    if not image_path.exists() or not image_path.is_file():
        logger.warning(f"Image not found: {filename}")
        raise HTTPException(status_code=404, detail="Image not found")

    # Verify the file is within the images directory (additional security)
    try:
        image_path.resolve().relative_to(IMAGES_DIR.resolve())
    except ValueError:
        logger.error(f"Attempted directory traversal: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Determine media type based on extension
    suffix = image_path.suffix.lower()
    media_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_type_map.get(suffix, 'application/octet-stream')

    return FileResponse(
        image_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=31536000",  # Cache for 1 year
        }
    )
