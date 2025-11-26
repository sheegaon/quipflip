"""Image serving router for Meme Mint."""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()

# Path to images directory (for local development)
IMAGES_DIR = Path(__file__).parent.parent.parent / "data" / "mm_images"


@router.get("/images/{filename}")
async def get_image(filename: str):
    """Serve an image file from the mm_images directory or redirect to GitHub.

    In production (Heroku), redirects to GitHub raw content URL.
    In local development, serves files directly from disk.

    Args:
        filename: Image filename (e.g., "image001.png")

    Returns:
        RedirectResponse to GitHub (production) or FileResponse (local)

    Raises:
        HTTPException: 400 for invalid filename, 404 if image not found
    """
    # Security: prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # In production or when configured, redirect to GitHub
    if settings.serve_images_from_github:
        github_url = f"{settings.github_images_base_url}/mm_images/{filename}"
        logger.info(f"Redirecting to GitHub: {github_url}")
        return RedirectResponse(
            url=github_url,
            status_code=302,  # Temporary redirect
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache redirect for 1 hour
            }
        )

    # Local development: serve from disk
    image_path = IMAGES_DIR / filename

    # Verify the file is within the images directory (additional security) -- BEFORE any filesystem access
    try:
        image_path_resolved = image_path.resolve()
        image_path_resolved.relative_to(IMAGES_DIR.resolve())
    except ValueError:
        logger.error(f"Attempted directory traversal: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not image_path.exists() or not image_path.is_file():
        logger.warning(f"Image not found: {filename}")
        raise HTTPException(status_code=404, detail="Image not found")

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
