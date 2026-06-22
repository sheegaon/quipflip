#!/bin/bash
# Deploy both backend and frontend
# Usage: ./scripts/deploy-all.sh [environment]

set -e

ENVIRONMENT=${1:-production}

echo "════════════════════════════════════════════════════════════"
echo "🚀 Initial Reaction Complete Deployment"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Environment: ${ENVIRONMENT}"
echo ""

# Deploy backend
echo "📦 Step 1: Deploying Backend..."
echo "─────────────────────────────────────────────────────────────"
./scripts/deploy-heroku.sh "${ENVIRONMENT}" || {
    echo "❌ Backend deployment failed"
    exit 1
}

echo ""
echo "Wait 30 seconds before frontend deployment..."
sleep 30

# Deploy frontend
echo ""
echo "📱 Step 2: Deploying Frontend..."
echo "─────────────────────────────────────────────────────────────"
./scripts/deploy-vercel.sh "${ENVIRONMENT}" || {
    echo "❌ Frontend deployment failed"
    exit 1
}

# Final summary
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Initial Reaction Deployment Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "🔗 Deployed URLs:"
echo "   Backend:  https://quipflip-c196034288cd.herokuapp.com/api/ir"
echo "   Frontend: https://ir.quipflip.com"
echo "   Docs:     https://quipflip-c196034288cd.herokuapp.com/docs"
echo ""
echo "📊 Monitoring:"
echo "   Backend Logs:  heroku logs --app quipflip-c196034288cd --tail"
echo "   Frontend:      https://vercel.com/dashboard"
echo ""
echo "🧪 Testing:"
echo "   Run tests: python -m pytest tests/test_ir_*.py -v"
echo ""
echo "Deployed by: deploy-all.sh"
echo "Timestamp: $(date)"
echo "════════════════════════════════════════════════════════════"
