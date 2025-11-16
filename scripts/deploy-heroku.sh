#!/bin/bash
# Deploy backend to Heroku
# Usage: ./scripts/deploy-heroku.sh [environment]

set -e

ENVIRONMENT=${1:-production}
HEROKU_APP="quipflip-c196034288cd"

echo "🚀 Deploying Initial Reaction backend to Heroku..."
echo "📦 Environment: ${ENVIRONMENT}"
echo "🔗 App: ${HEROKU_APP}"

# Verify we're on main branch for production
if [ "${ENVIRONMENT}" = "production" ]; then
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "${CURRENT_BRANCH}" != "main" ]; then
        echo "❌ Error: Production deployments must be from main branch"
        echo "   Current branch: ${CURRENT_BRANCH}"
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "❌ Error: Uncommitted changes detected"
    echo "   Please commit or stash changes before deploying"
    exit 1
fi

# Run tests before deployment
echo "🧪 Running backend tests..."
python -m pytest tests/test_ir_*.py -v --tb=short || {
    echo "❌ Tests failed. Aborting deployment."
    exit 1
}

# Run migrations
echo "📊 Running database migrations..."
alembic upgrade head

# Deploy to Heroku
echo "📤 Pushing to Heroku..."
git push heroku main

# Run post-deployment checks
echo "✅ Checking deployment..."
sleep 5

# Verify API is healthy
API_URL="https://${HEROKU_APP}.herokuapp.com/api/ir/health"
if curl -f -s "${API_URL}" > /dev/null; then
    echo "✅ API is healthy"
else
    echo "⚠️  Could not verify API health"
    echo "   Check logs: heroku logs --app ${HEROKU_APP} --tail"
fi

echo ""
echo "✨ Backend deployment complete!"
echo "📍 URL: https://${HEROKU_APP}.herokuapp.com"
echo "📋 Logs: heroku logs --app ${HEROKU_APP} --tail"
