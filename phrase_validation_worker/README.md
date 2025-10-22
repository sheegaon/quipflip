# Phrase Validation Worker

A standalone FastAPI service that validates Quipflip phrases. The worker exposes
HTTP endpoints that the main backend calls to approve prompt and copy phrases.
It can be deployed independently (for example, on a separate Heroku app).

## Features

- Dictionary based validation with connector word exceptions
- Similarity checks using sentence-transformers or a TF-IDF fallback
- Prompt relevance enforcement and duplicate detection
- REST API with `/validate`, `/validate/prompt`, and `/validate/copy`
- Configurable entirely via environment variables

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Copy the example environment file and adjust values as needed
cp .env.example .env

# Run the service
uvicorn phrase_validation_worker.main:app --reload --port 9000
```

The service exposes OpenAPI docs at <http://localhost:9000/docs>.

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `ENVIRONMENT` | Environment label written to logs | `development` |
| `USE_SENTENCE_TRANSFORMERS` | Enable the sentence-transformers model | `true` |
| `SIMILARITY_MODEL` | Sentence-transformers model name | `paraphrase-MiniLM-L6-v2` |
| `SIMILARITY_THRESHOLD` | Maximum similarity allowed between copy phrases | `0.8` |
| `PROMPT_RELEVANCE_THRESHOLD` | Minimum similarity between prompt and phrase | `0.1` |
| `WORD_SIMILARITY_THRESHOLD` | Ratio used to detect overly similar words | `0.8` |
| `DICTIONARY_PATH` | Override dictionary path | `data/dictionary.txt` |

## Docker

A dedicated Dockerfile is provided:

```bash
docker build -t phrase-validator .
docker run -p 9000:9000 --env-file .env phrase-validator
```

## Heroku Deployment

Use the included `heroku.yml` for Container Registry deployments:

```bash
heroku create your-validator-app
heroku stack:set container --app your-validator-app
heroku container:push web --app your-validator-app
heroku container:release web --app your-validator-app
```

Ensure the main Quipflip backend sets `PHRASE_VALIDATOR_URL` to the deployed
Heroku app URL.

## Dictionary

The worker ships with a lightweight sample dictionary in `data/dictionary.txt`.
Generate a fresh copy using the shared script from the repository root:

```bash
python scripts/download_dictionary.py
```

Replace the dictionary with the official tournament word list before production
use.
