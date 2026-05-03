# Vercel + Railway Deployment Checklist

Complete this checklist to deploy L4RPCH3KR to production.

## Pre-Deployment Setup

### Local Environment
- [ ] Node.js 18+ installed (`node --version`)
- [ ] Python 3.9+ installed (`python --version`)
- [ ] All dependencies installed:
  - [ ] Dashboard: `cd dashboard && npm install`
  - [ ] Backend: `cd backend && pip install -r requirements.txt`
- [ ] Project tested locally:
  - [ ] Dashboard: `npm run dev` in dashboard/
  - [ ] Backend: `uvicorn app.main:app` in backend/
- [ ] Git repository is clean: `git status` shows no uncommitted changes
- [ ] Latest code pushed to GitHub: `git push origin main`

### Accounts & Access
- [ ] Vercel account created (https://vercel.com) - recommend GitHub OAuth login
- [ ] Railway account created (https://railway.app) - recommend GitHub OAuth login
- [ ] Both connected to GitHub Bot-106 account
- [ ] MongoDB Atlas account (optional, for cloud MongoDB)
  - [ ] Or plan to use Railway's free MongoDB instance

### Configuration Files Created
- [ ] `vercel.json` ✓
- [ ] `.vercelignore` ✓
- [ ] `backend/Procfile` ✓
- [ ] `dashboard/src/lib/api-keys.ts` ✓
- [ ] `dashboard/src/app/settings/page.tsx` ✓
- [ ] `backend/app/llm_keys.py` ✓
- [ ] Documentation files:
  - [ ] `VERCEL_DEPLOYMENT.md` ✓
  - [ ] `backend/RAILWAY_DEPLOYMENT.md` ✓

## Dashboard Deployment (Vercel)

### Create Vercel Project
- [ ] Go to https://vercel.com/new
- [ ] Select "Import Git Repository"
- [ ] Search for and select `Bot-106/L4RPCH3KR`
- [ ] Project name: `larpchekr-dashboard` (or custom)
- [ ] Root directory: `dashboard/`
- [ ] Framework: Next.js (auto-detected)
- [ ] Build command: `npm run build`
- [ ] Node.js version: 20.x

### Set Environment Variables (Vercel)
- [ ] Add variable: `NEXT_PUBLIC_API_BASE`
  - [ ] Value: `http://localhost:8000` (temporary, for testing)
  - [ ] Will update after backend deploys
- [ ] Click "Deploy"
- [ ] Wait for build to complete (~5-10 minutes)
- [ ] Deployment successful? ✓ You'll get a URL like `https://larpchekr-dashboard-xxx.vercel.app`

### Test Dashboard
- [ ] Visit the Vercel URL in browser
- [ ] Page loads without errors
- [ ] Navigation works (EVENTS, LARPERBOARD, SETTINGS)
- [ ] Can navigate to /settings page

## Backend Deployment (Railway)

### Create Railway Project
- [ ] Go to https://railway.app/new
- [ ] Click "Deploy from GitHub repo"
- [ ] Select `Bot-106/L4RPCH3KR`
- [ ] Choose branch: `main`
- [ ] Railway auto-detects and starts building

### Add MongoDB Service
- [ ] While project is building, click "+ Add Service"
- [ ] Select "MongoDB"
- [ ] Railway provisions a free MongoDB instance
- [ ] Copy the generated `MONGO_URL` connection string

### Set Environment Variables (Railway)
In Railway dashboard, go to **Variables** tab and add:

**Database Configuration**
- [ ] `MONGO_URL`: (paste from MongoDB service creation)
- [ ] `MONGO_DB`: `larpchekr`

**Security**
- [ ] `JWT_SECRET`: (generate with: `openssl rand -hex 32`)

**LLM Configuration** (users will provide via Settings page)
- [ ] `LLM_PROVIDER`: `anthropic`
- [ ] `ANTHROPIC_API_KEY`: (leave empty)
- [ ] `OPENAI_API_KEY`: (leave empty)
- [ ] `LLM_MODEL`: `claude-haiku-4-5`

**Whisper Configuration**
- [ ] `WHISPER_MODEL`: `small.en`
- [ ] `WHISPER_DEVICE`: `auto`
- [ ] `WHISPER_COMPUTE_TYPE`: `auto`
- [ ] `ASR_CHUNK_SECONDS`: `3.0`

**CORS Configuration**
- [ ] `CORS_ORIGINS`: (update with your Vercel dashboard URL from above)
  - [ ] Format: `https://larpchekr-dashboard-xxx.vercel.app,http://localhost:3000`

**Optional Services**
- [ ] `RESEND_API_KEY`: (if using email magic links)
- [ ] `GITHUB_OAUTH_CLIENT_ID`: (if using GitHub OAuth)
- [ ] `GITHUB_OAUTH_CLIENT_SECRET`: (if using GitHub OAuth)
- [ ] `LINKEDIN_EMAIL`: (if scraping LinkedIn)
- [ ] `LINKEDIN_PASSWORD`: (if scraping LinkedIn)
- [ ] `LINKEDIN_COOKIE`: (if scraping LinkedIn)

**Storage**
- [ ] `STORAGE_BACKEND`: `local`

### Deploy Backend
- [ ] All environment variables set
- [ ] Click "Deploy" or trigger via GitHub push
- [ ] Wait for build & deployment (~10-15 minutes)
- [ ] Deployment successful? ✓ Check Deployments tab

### Get Backend URL
- [ ] Go to Railway project → **Settings**
- [ ] Copy the domain under "Domains" (looks like: `larpchekr-backend-prod.railway.app`)

### Test Backend
- [ ] Visit `https://larpchekr-backend-prod.railway.app/docs` in browser
- [ ] FastAPI Swagger docs load successfully
- [ ] Test GET `/` endpoint (should return API info)

## Connect Dashboard & Backend

### Update Dashboard Environment
- [ ] Go to Vercel project → **Settings** → **Environment Variables**
- [ ] Edit `NEXT_PUBLIC_API_BASE` variable
- [ ] Change from `http://localhost:8000` to your Railway URL
- [ ] Value: `https://larpchekr-backend-prod.railway.app`
- [ ] Save
- [ ] Vercel automatically rebuilds and redeploys

### Test Integration
- [ ] Dashboard at Vercel URL loads
- [ ] Go to /events (might require sign-in first)
- [ ] Check browser console for errors
- [ ] Network tab shows requests to your Railway URL

## API Key Management Setup

### Configure Dashboard Settings Page
- [ ] Users can navigate to `/settings`
- [ ] Two input fields: Anthropic API Key, OpenAI API Key
- [ ] Keys stored in browser cookies (not sent to server)
- [ ] Can save/clear keys

### Configure Backend to Accept Custom Keys
- [ ] Backend code has `app/llm_keys.py` utility ✓
- [ ] LLM endpoints check for `X-LLM-API-Key` header
- [ ] Falls back to `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` from env if custom not provided

### Test Custom Keys
- [ ] Go to Dashboard → Settings
- [ ] Enter a test Anthropic API key
- [ ] Click "Save Key"
- [ ] Verify it appears saved
- [ ] Use a feature that calls the LLM (claim extraction, etc.)
- [ ] Verify it works with custom key instead of server key

## Domain Configuration (Optional)

### Custom Domain for Dashboard
- [ ] Own a domain? (e.g., `dashboard.larpchekr.app`)
- [ ] In Vercel project → **Settings** → **Domains**
- [ ] Add your custom domain
- [ ] Follow DNS setup instructions from Vercel
- [ ] Test domain in browser

### Custom Domain for Backend
- [ ] In Railway project → **Settings** → **Domains**
- [ ] Add custom domain (e.g., `api.larpchekr.app`)
- [ ] Update `NEXT_PUBLIC_API_BASE` in Vercel if using custom domain
- [ ] Test API at custom domain

## Monitoring & Alerts

### Vercel Monitoring
- [ ] Set up GitHub integration (should be automatic)
- [ ] Check **Analytics** tab for traffic
- [ ] Review **Deployments** for build history
- [ ] Set up email notifications for deployments

### Railway Monitoring
- [ ] Visit **Monitoring** tab
- [ ] Check CPU/Memory/Network graphs
- [ ] Set up failure notifications
- [ ] Review **Logs** periodically for errors

### Logging & Debugging
- [ ] Dashboard errors: Check Vercel Deployments → Logs
- [ ] Backend errors: Check Railway Deployments → Logs
- [ ] Browser errors: Check browser DevTools → Console
- [ ] Network errors: Check browser DevTools → Network tab

## Testing Workflow

### Full End-to-End Test
1. [ ] Visit Dashboard URL
2. [ ] Navigate to /events (sign in if needed)
3. [ ] Navigate to /settings
4. [ ] Enter a test API key
5. [ ] Use a feature that calls LLM (verify custom key used)
6. [ ] Check backend logs for requests
7. [ ] Verify API key headers received

### Failure Recovery Tests
1. [ ] Backend URL wrong in Vercel:
   - [ ] Update environment variable
   - [ ] Redeploy dashboard
   - [ ] Verify fix
2. [ ] Backend not responding:
   - [ ] Check Railway Deployments → Logs
   - [ ] Restart the service
   - [ ] Check MongoDB connection
3. [ ] MongoDB connection fails:
   - [ ] Verify MONGO_URL is correct
   - [ ] Check MongoDB service is running in Railway
   - [ ] Restart MongoDB

## Post-Deployment Checklist

### Security
- [ ] No sensitive data in `.env` files (use Railway/Vercel variables)
- [ ] API keys not logged or exposed in console
- [ ] CORS origins whitelist only your domains
- [ ] JWT_SECRET is a strong random value (generated with openssl)
- [ ] No default/hardcoded passwords

### Performance
- [ ] Dashboard loads in < 3 seconds
- [ ] API responses < 1 second (excluding LLM calls)
- [ ] Database queries optimized (check MongoDB indexes)
- [ ] No console warnings/errors in production

### Documentation
- [ ] VERCEL_DEPLOYMENT.md is accurate
- [ ] RAILWAY_DEPLOYMENT.md is accurate
- [ ] Team knows how to access logs
- [ ] Team knows how to update environment variables
- [ ] Team knows rollback procedure

### Team Handoff
- [ ] Everyone has access to Vercel project
- [ ] Everyone has access to Railway project
- [ ] Deployment credentials documented somewhere safe
- [ ] Runbook created for common issues
- [ ] Escalation contacts documented

## Verification

### Final Verification Checklist
- [ ] Both Vercel and Railway projects deployed
- [ ] Dashboard loads without errors
- [ ] Backend API responding
- [ ] API keys workflow works
- [ ] Logs accessible
- [ ] Team can deploy changes
- [ ] Backup/recovery procedure in place

---

## Deployment Summary

| Component | Platform | URL | Status |
|-----------|----------|-----|--------|
| Dashboard | Vercel | `https://larpchekr-dashboard-xxx.vercel.app` | [ ] |
| Backend | Railway | `https://larpchekr-backend-prod.railway.app` | [ ] |
| MongoDB | Railway | (internal) | [ ] |

## Rollback Procedure

### Revert Dashboard
1. Vercel → Deployments tab
2. Find previous successful deployment
3. Click "Promote to Production"
4. Verify deployment is live

### Revert Backend
1. Railway → Deployments tab
2. Find previous successful deployment
3. Click "Revert" or redeploy specific version
4. Verify service is healthy

---

Date Deployed: _____________
Deployed By: _____________
Notes: _____________
