# Meme Mint Image Management

This directory contains the image management system for Meme Mint.

## Directory Structure

```
backend/data/
├── mm_images/           # Image files (.jpg, .jpeg, .png, .gif, .webp)
│   └── image001.png     # Example image
├── mm_seed_captions.csv # Seed captions for each image
└── import_mm_images.py  # Import script
```

## Production vs Development

### Production (Heroku)
- Images are **NOT** included in the Docker image (saves space)
- API endpoint `/api/mm/images/{filename}` redirects to GitHub raw content
- Images served from: `https://raw.githubusercontent.com/sheegaon/quipflip/main/backend/data/mm_images/`
- Configured via environment variables:
  ```
  SERVE_IMAGES_FROM_GITHUB=true
  GITHUB_IMAGES_BASE_URL=https://raw.githubusercontent.com/sheegaon/quipflip/main/backend/data
  ```

### Local Development
- Images served directly from `backend/data/mm_images/` directory
- Set environment variable to serve locally:
  ```
  SERVE_IMAGES_FROM_GITHUB=false
  ```
- Or leave unset (defaults to serving from GitHub in config)

## Adding New Images

### 1. Add Image File

Copy your image file to `backend/data/mm_images/`:

```bash
cp /path/to/your/image.png backend/data/mm_images/
```

Supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

### 2. Run Import Script

```bash
PYTHONPATH=/Users/tfish/PycharmProjects/quipflip .venv/bin/python backend/data/import_mm_images.py
```

The script will:
- ✅ Auto-detect all images in `mm_images/`
- ✅ Create `MMImage` records for new images
- ✅ Create `MMCaption` records for seed captions
- ✅ Skip images and captions that already exist
- ✅ Set image URLs to `/api/mm/images/{filename}`

### 3. Commit to GitHub

For production deployment, commit the images to GitHub:

```bash
git add backend/data/mm_images/your_image.png
git add backend/data/mm_seed_captions.csv
git commit -m "Add new meme image: your_image.png"
git push origin main
```

The images will be automatically served from GitHub in production.

## Import Script Behavior

### Idempotent Operation
The import script is safe to run multiple times:
- Existing images are skipped (matched by `source_url`)
- Existing captions are skipped (matched by `text` for each image)
- Only new images and captions are added

### Output
The script provides detailed logging:
```
INFO:__main__:Found 3 image files in /path/to/mm_images
INFO:__main__:Created image: image2.png (ID: ...)
INFO:__main__:Added 5 captions for image2.png
INFO:__main__:Import complete:
  - Images created: 2
  - Captions created: 10
  - Total images in directory: 3
```

## Image Serving

### API Endpoint
```
GET /api/mm/images/{filename}
```

### Behavior
- **Production**: Returns 302 redirect to GitHub raw content URL
- **Development**: Serves file directly from disk

### Example
```bash
# Production
curl -L https://quipflip.herokuapp.com/api/mm/images/image001.png
# → Redirects to GitHub

# Local development
curl http://localhost:8000/api/mm/images/image001.png
# → Serves from backend/data/mm_images/image001.png
```

## Configuration

### Environment Variables

Set these in your `.env` file or Heroku config:

```bash
# Serve images from GitHub (production)
SERVE_IMAGES_FROM_GITHUB=true
GITHUB_IMAGES_BASE_URL=https://raw.githubusercontent.com/sheegaon/quipflip/main/backend/data

# Or serve locally (development)
SERVE_IMAGES_FROM_GITHUB=false
```

### Docker Exclusions

Images are excluded from Docker builds via `.dockerignore`:

```
backend/data/mm_images/
backend/data/*.png
backend/data/*.jpg
backend/data/*.jpeg
backend/data/*.gif
backend/data/*.webp
```

This keeps the Docker image small and fast to deploy.

## Tips

### Quality Captions
Good seed captions are:
- Universal (work for many images)
- Relatable
- Short and punchy (1-10 words)
- Use common meme formats

### Caption Examples
```
"When you finally understand the assignment"
"Me pretending to be productive"
"That moment when everything clicks"
"Monday mood"
"Living my best life"
"This is fine"
"Big mood energy"
"Plot twist: it gets worse"
"Nobody asked but here we are"
"The accuracy is unsettling"
```

### Bulk Import
To add many images at once:
1. Copy all image files to `mm_images/`
2. Add all rows to `mm_seed_captions.csv` (use spreadsheet for easy editing)
3. Run the import script once

The script processes all images in a single transaction.

## Troubleshooting

### Image Not Found in Production
Make sure:
- Image is committed to GitHub
- Filename matches exactly (case-sensitive)
- GitHub URL is correct in config

### Image Not Found in Development
Make sure:
- File is in `backend/data/mm_images/`
- File extension is supported (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`)
- Filename matches exactly (case-sensitive)
- `SERVE_IMAGES_FROM_GITHUB=false` is set

### Caption Not Created
Check:
- CSV has the correct filename
- Caption text is properly quoted
- Caption doesn't already exist for that image (case-insensitive duplicate check)

### Database Connection
Make sure database is running and `DATABASE_URL` is set correctly in your environment or `.env` file.
