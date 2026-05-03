# Vercel Deployment Guide

This guide explains how to deploy L4RPCH3KR to Vercel.

## Project Structure

L4RPCH3KR is a monorepo with multiple components:

- **Dashboard** (`dashboard/`) - Next.js web app for event organizers
- **Backend** (`backend/`) - FastAPI Python server (requires separate deployment)
- **Web Phone** (`web-phone/`) - React PWA for attendees (optional, not deployed to Vercel here)
- **Pi** (`pi/`) - Raspberry Pi wearable code (not deployed)

## Deployment Strategy

### Dashboard → Vercel ✅

The **Next.js Dashboard** is perfect for Vercel's serverless infrastructure.

### Backend → Railway/Render/Alternative ⚠️

Vercel primarily supports Node.js for serverless functions. The FastAPI backend is Python-based and better suited for:

- **Railway.app** (recommended) - Great Python support, simple deployment
- **Render.com** - Free tier available, easy setup
- **PythonAnywhere** - Python-specific hosting
- **AWS Lambda** - With serverless framework wrapper

## Step 1: Deploy Dashboard to Vercel

### Prerequisites

- Vercel account (free tier available)
- GitHub repository with this code
- Node.js 18+ installed locally

### Deploy Steps

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Add Vercel configuration"
   git push origin main
   ```

2. **Visit Vercel Dashboard**:
   - Go to https://vercel.com/new
   - Select GitHub (authorize if needed)
   - Find and select `Bot-106/L4RPCH3KR` repo

3. **Configure Project**:
   - **Framework**: Next.js (auto-detected)
   - **Root Directory**: `dashboard/`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
   - **Node.js Version**: 20.x (recommended)

4. **Set Environment Variables**:
   Click "Environment Variables" and add:

   ```
   NEXT_PUBLIC_API_BASE=https://your-backend-url.com
   ```

   Replace `https://your-backend-url.com` with your backend's actual URL (Railway/Render domain).

5. **Deploy**:
   - Click "Deploy"
   - Vercel will build and deploy automatically
   - Your dashboard will be available at something like: `https://larpchekr-dashboard-xxx.vercel.app`

6. **Configure Custom Domain** (optional):
   - In Vercel dashboard, go to project settings
   - Add your custom domain (e.g., `dashboard.larpchekr.app`)
   - Update DNS records as instructed

## Step 2: Deploy Backend to Railway.app (Recommended)

### Why Railway?

- Excellent Python support
- Simple environment variable management
- Can host MongoDB or use MongoDB Atlas
- Free tier generous enough for testing

### Deploy Steps

1. **Create Railway Account**:
   - Go to https://railway.app
   - Sign up with GitHub

2. **Create New Project**:
   - Click "Create New Project"
   - Select "Deploy from GitHub repo"
   - Authorize and select `Bot-106/L4RPCH3KR`

3. **Add Services**:
   - Add MongoDB (Railway provides a free MongoDB instance)
   - Or connect to MongoDB Atlas (cloud-hosted)

4. **Configure Environment Variables**:
   - In Railway dashboard, go to Variables
   - Add all from `backend/.env`:

   ```
   MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net
   MONGO_DB=larpchekr
   JWT_SECRET=<generate with: openssl rand -hex 32>
   FIXTURE_MODE=false
   
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=<leave empty, users will provide via browser>
   OPENAI_API_KEY=<leave empty, users will provide via browser>
   LLM_MODEL=claude-haiku-4-5
   
   CORS_ORIGINS=https://larpchekr-dashboard-xxx.vercel.app,http://localhost:3000
   
   STORAGE_BACKEND=local
   ```

   **Important**: Leave `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` empty. Users will provide their own via the Settings page in the dashboard.

5. **Set Up Procfile** (if needed):
   Create `backend/Procfile`:
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

6. **Deploy**:
   - Railway auto-deploys from GitHub
   - Your backend URL will be like: `https://larpchekr-backend.railway.app`

7. **Update Dashboard**:
   - Go back to Vercel dashboard settings
   - Update `NEXT_PUBLIC_API_BASE` to your Railway URL
   - Vercel will rebuild automatically

## API Key Management

Users can now provide their own API keys **without server-side secrets**:

1. **In Dashboard**:
   - Navigate to `/settings`
   - Enter Anthropic or OpenAI API key
   - Keys are stored in browser cookies (not sent to server)

2. **How It Works**:
   - Frontend stores keys in `HttpOnly` cookies
   - When making API calls, frontend includes headers:
     ```
     X-LLM-API-Key: <user's key>
     X-LLM-Provider: anthropic|openai
     ```
   - Backend uses custom key if provided, falls back to `settings` if not
   - Backend code updated to accept custom keys via `llm_keys.py`

## Environment Variables Reference

### Dashboard (Vercel)

```
NEXT_PUBLIC_API_BASE=https://your-backend-url.com
```

### Backend (Railway)

Required:
- `MONGO_URL` - MongoDB connection string
- `MONGO_DB` - Database name (default: `larpchekr`)
- `JWT_SECRET` - Generate with: `openssl rand -hex 32`
- `LLM_PROVIDER` - `anthropic` or `openai`
- `LLM_MODEL` - Model name (e.g., `claude-haiku-4-5`)

Optional (users can provide via Settings page):
- `ANTHROPIC_API_KEY` - Leave empty, users provide via browser
- `OPENAI_API_KEY` - Leave empty, users provide via browser

Other:
- `CORS_ORIGINS` - Comma-separated list of allowed frontend URLs
- `STORAGE_BACKEND` - `local` or `s3`
- `FIXTURE_MODE` - `true` or `false`

## Troubleshooting

### Dashboard won't build
- Check Node.js version: `node --version` (should be 18+)
- Clear node_modules: `rm -rf dashboard/node_modules && npm install`
- Check `dashboard/tsconfig.json` is valid

### Backend won't start
- Check Python version: `python --version` (should be 3.9+)
- Install dependencies: `pip install -r backend/requirements.txt`
- Check `.env` has valid MongoDB URL

### CORS errors
- Update `CORS_ORIGINS` in backend to include your Vercel dashboard URL
- Format: `https://yourdomain.vercel.app`

### API Key not working
- Ensure `X-LLM-API-Key` and `X-LLM-Provider` headers are sent
- Check key is valid format (starts with `sk-`)
- Verify `llm_keys.py` is imported in relevant modules

## Monitoring & Logs

### Vercel
- Logs available in Vercel dashboard → project → Deployments → Logs
- Check for build errors first

### Railway
- Logs in Railway dashboard → project → Deployments → Logs
- Monitor resource usage in Dashboard tab

## Rollback

### Vercel
- Go to Deployments tab
- Click "Promote" on previous successful deployment

### Railway
- Go to Deployments tab
- Redeploy previous version

## Next Steps

1. ✅ Set up Dashboard on Vercel
2. ✅ Deploy Backend to Railway
3. ✅ Configure environment variables
4. ✅ Test API connectivity
5. ✅ Add custom domain (optional)
6. ✅ Set up monitoring alerts
