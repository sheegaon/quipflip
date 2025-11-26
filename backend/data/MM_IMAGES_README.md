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

## Adding New Images

### 1. Add Image File

Copy your image file to `backend/data/mm_images/`:

```bash
cp /path/to/your/image.jpg backend/data/mm_images/
```

Supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

### 2. Add Seed Captions

Edit `mm_seed_captions.csv` and add a row for your image:

```csv
image_file,seed_caption1,seed_caption2,seed_caption3,seed_caption4,seed_caption5
your_image.png,"First caption","Second caption","Third caption","Fourth caption","Fifth caption"
```

**Notes:**
- You can add more than 5 captions by adding columns: `seed_caption6`, `seed_caption7`, etc.
- Captions should be quoted if they contain commas
- Lines starting with `#` are treated as comments and ignored

### 3. Run Import Script

```bash
PYTHONPATH=/Users/tfish/PycharmProjects/quipflip .venv/bin/python backend/data/import_mm_images.py
```

The script will:
- ✅ Auto-detect all images in `mm_images/`
- ✅ Create `MMImage` records for new images
- ✅ Create `MMCaption` records for seed captions
- ✅ Skip images and captions that already exist
- ✅ Set image URLs to `/api/mm/images/{filename}`

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
INFO:__main__:Created image: image2.jpeg (ID: ...)
INFO:__main__:Added 5 captions for image2.jpeg
INFO:__main__:Import complete:
  - Images created: 2
  - Captions created: 10
  - Total images in directory: 3
```

## Image Serving

Images are served by the FastAPI backend at:
```
GET /api/mm/images/{filename}
```

The router for this endpoint should be implemented in `backend/routers/mm/images.py`.

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

### Image Not Found
Make sure:
- File is in `backend/data/mm_images/`
- File extension is supported (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`)
- Filename matches exactly (case-sensitive)

### Caption Not Created
Check:
- CSV has the correct filename
- Caption text is properly quoted
- Caption doesn't already exist for that image (case-insensitive duplicate check)

### Database Connection
Make sure database is running and `DATABASE_URL` is set correctly in your environment or `.env` file.
