#!/bin/bash
# Deploy frontend to Vercel
# Usage: ./scripts/deploy-vercel.sh [environment]

set -e

ENVIRONMENT=${1:-production}
VERCEL_PROJECT_NAME="ir-frontend"

echo "🚀 Deploying Initial Reaction frontend to Vercel..."
echo "📦 Environment: ${ENVIRONMENT}"
echo "🔗 Project: ${VERCEL_PROJECT_NAME}"

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

cd frontend/ir

# Install dependencies
echo "📦 Installing dependencies..."
npm install --prefer-offline

# Run linter
echo "🧹 Running linter..."
npm run lint || {
    echo "❌ Linting failed. Aborting deployment."
    exit 1
}

# Build frontend
echo "🔨 Building frontend..."
npm run build || {
    echo "❌ Build failed. Aborting deployment."
    exit 1
}

# Verify Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "📥 Installing Vercel CLI..."
    npm install -g vercel
fi

# Deploy based on environment
if [ "${ENVIRONMENT}" = "production" ]; then
    echo "📤 Deploying to production..."
    vercel deploy --prod
    DEPLOY_URL="https://ir.quipflip.com"
else
    echo "📤 Deploying to preview..."
    DEPLOY_URL=$(vercel deploy)
fi

echo ""
echo "✨ Frontend deployment complete!"
echo "📍 URL: ${DEPLOY_URL}"
echo "🌐 Dashboard: https://vercel.com/dashboard"

cd ../..
