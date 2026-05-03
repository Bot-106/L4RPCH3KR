#!/bin/bash

# Quick Start: Deploy L4RPCH3KR to Vercel + Railway
# This script provides step-by-step instructions for deploying both components

set -e

echo "=========================================="
echo "L4RPCH3KR DEPLOYMENT SETUP"
echo "=========================================="
echo ""

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "⚠️  Vercel CLI not found. Installing..."
    npm install -g vercel
fi

echo "✓ Prerequisites checked"
echo ""

echo "=========================================="
echo "STEP 1: Dashboard Deployment (Vercel)"
echo "=========================================="
echo ""
echo "Starting Vercel deployment for Dashboard..."
echo "Follow the prompts to:"
echo "  1. Link to GitHub account"
echo "  2. Select Bot-106/L4RPCH3KR repo"
echo "  3. Set root directory: dashboard/"
echo ""

cd dashboard
vercel
cd ..

echo ""
echo "=========================================="
echo "STEP 2: Backend Deployment (Railway)"
echo "=========================================="
echo ""
echo "Next, deploy the backend to Railway:"
echo "  1. Go to https://railway.app/new"
echo "  2. Create project from GitHub repo"
echo "  3. Select Bot-106/L4RPCH3KR"
echo "  4. Add MongoDB service (free tier)"
echo "  5. Set environment variables (see RAILWAY_DEPLOYMENT.md)"
echo ""

echo "=========================================="
echo "STEP 3: Connect Components"
echo "=========================================="
echo ""
echo "After both deployments complete:"
echo "  1. Get your Railway backend URL from Railway dashboard"
echo "  2. In Vercel project settings, add environment variable:"
echo "     NEXT_PUBLIC_API_BASE=<your-railway-url>"
echo "  3. Vercel will auto-rebuild with the new URL"
echo ""

echo "✓ Setup complete! Check the logs for any errors."
