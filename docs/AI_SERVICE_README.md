# AI Copy Service

This module provides AI-powered backup copy generation for the Quipflip game when human players are unavailable.

## Architecture

The AI copy service supports multiple AI providers with automatic fallback:

```
ai_copy_service.py (orchestrator)
├── openai_api.py (OpenAI provider)
├── gemini_api.py (Gemini provider)
└── prompt_builder.py (shared prompt logic)
```

## Supported Providers

### OpenAI (Default)
- **Model**: GPT-5 Nano (configurable via `AI_COPY_OPENAI_MODEL`)
- **API Key**: Set `OPENAI_API_KEY` environment variable
- **Advantages**: High-quality responses, well-tested

### Gemini
- **Model**: gemini-2.5-flash-lite (configurable via `AI_COPY_GEMINI_MODEL`)
- **API Key**: Set `GEMINI_API_KEY` environment variable
- **Advantages**: Fast responses, cost-effective

## Configuration

Add to your `.env` file:

```bash
# AI Provider Selection
AI_COPY_PROVIDER=openai  # Options: "openai" or "gemini"

# API Keys (at least one required)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Model Configuration (optional, uses defaults if not set)
AI_COPY_OPENAI_MODEL=gpt-5-nano
AI_COPY_GEMINI_MODEL=gemini-2.5-flash-lite

# Service Configuration
AI_COPY_TIMEOUT_SECONDS=30
AI_BACKUP_DELAY_MINUTES=10
```

## Provider Selection Logic

1. Use configured provider if API key is available
2. Fall back to other provider if configured one is unavailable
3. Default to OpenAI if both are available
4. Raise error if no provider is configured

## Usage

### From Code

```python
from backend.services.ai_copy_service import AICopyService
from backend.services.phrase_validator import PhraseValidator

# Initialize service
validator = PhraseValidator(db)
ai_service = AICopyService(db, validator)

# Generate a copy phrase
try:
    copy_phrase = await ai_service.generate_copy_phrase(
        original_phrase="happy day",
        prompt_text="A feeling of joy"
    )
    print(f"AI generated: {copy_phrase}")
except AICopyError as e:
    print(f"Error: {e}")
```

### Background Service

The AI backup cycle runs periodically to provide copies for waiting prompts:

```python
stats = await ai_service.run_backup_cycle()
print(f"Generated {stats['copies_generated']} backup copies")
```

## Implementation Details

### Transaction Management

- `_get_or_create_ai_player()` does NOT commit transactions
- Transaction lifecycle is managed by `run_backup_cycle()`
- This prevents partial state if the backup cycle fails

### Prompt Building

Shared prompt logic in `prompt_builder.py` ensures:
- Consistent prompt format across providers
- No code duplication
- Easy maintenance and updates

### Validation

All AI-generated phrases are validated using the same rules as human submissions:
- 1-5 words
- 2-100 characters total
- A-Z and spaces only
- Dictionary validation
- Similarity checking

## Error Handling

The service handles errors gracefully:

```python
try:
    phrase = await ai_service.generate_copy_phrase(...)
except AICopyError as e:
    # Provider-specific error (API key missing, timeout, etc.)
    logger.error(f"AI copy failed: {e}")
```

## Testing

### Manual Testing

Test individual providers:

```bash
# Test Gemini
python -c "from backend.services import gemini_api; import asyncio; print(asyncio.run(gemini_api.generate_copy('happy day', 'A feeling of joy')))"

# Test OpenAI
python -c "from backend.services import openai_api; import asyncio; print(asyncio.run(openai_api.generate_copy('happy day', 'A feeling of joy')))"
```

### Integration Testing

```python
import pytest
from backend.services.ai_copy_service import AICopyService

@pytest.mark.asyncio
async def test_ai_copy_generation(db_session, phrase_validator):
    service = AICopyService(db_session, phrase_validator)
    result = await service.generate_copy_phrase(
        original_phrase="test phrase",
        prompt_text="test prompt"
    )
    assert result is not None
    assert len(result) > 0
```

## Future Enhancements

1. **AI Voting**: Generate AI votes when voters are unavailable
2. **Quality Metrics**: Track AI success rates and adjust models
3. **Cost Tracking**: Monitor API usage and costs per provider
4. **A/B Testing**: Compare provider performance
5. **Caching**: Cache similar prompts to reduce API calls
6. **Rate Limiting**: Prevent excessive API usage

## Troubleshooting

### "No AI provider configured" Error

**Cause**: Neither `OPENAI_API_KEY` nor `GEMINI_API_KEY` is set.

**Solution**: Add at least one API key to your `.env` file.

### Import Errors

**Cause**: Required packages not installed.

**Solution**:
```bash
pip install openai>=1.0.0 google-genai==1.45.0
```

### Provider Fallback Not Working

**Cause**: Configured provider has invalid API key.

**Solution**: Check API key validity and permissions.

## Security Considerations

- Store API keys in environment variables, never in code
- Use `.env` file for local development (gitignored)
- Use platform-specific secrets management in production (Heroku Config Vars)
- Monitor API usage to detect anomalies
- Implement rate limiting to prevent abuse

## Cost Optimization

- OpenAI: ~$0.0001 per copy generation (GPT-5 Nano)
- Gemini: ~$0.00005 per copy generation (Flash Lite)
- Expected usage: ~100-500 AI copies per day
- Estimated monthly cost: $1-5

To minimize costs:
1. Set `AI_BACKUP_DELAY_MINUTES` higher (e.g., 15-20 minutes)
2. Use Gemini as primary provider (faster and cheaper)
3. Monitor usage via provider dashboards
