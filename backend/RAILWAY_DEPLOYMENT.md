# Railway Deployment Quick Start

## Prerequisites

- Railway.app account (https://railway.app - free tier available)
- GitHub account connected to Railway
- This repo pushed to GitHub

## One-Click Deploy

1. **Go to Railway Dashboard**: https://railway.app/new

2. **Create Project from Repository**:
   - Click "Deploy from GitHub repo"
   - Select `Bot-106/L4RPCH3KR`
   - Choose branch: `main`

3. **Railway will auto-detect**:
   - It sees `backend/Procfile` and knows how to start the app
   - It sees `backend/requirements.txt` and installs Python dependencies

4. **Add MongoDB Service**:
   - Click "+ Add Service"
   - Select "MongoDB"
   - Railway creates a free MongoDB instance for you
   - Copy the connection string it provides

5. **Set Environment Variables**:
   In Railway project dashboard, go to **Variables** and add:

   ```
   # Database
   MONGO_URL=<paste the MongoDB URL from step 4>
   MONGO_DB=larpchekr
   
   # JWT - Generate with: openssl rand -hex 32
   JWT_SECRET=<generate a random hex string>
   
   # LLM Configuration - Users will provide keys via Settings page
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=
   OPENAI_API_KEY=
   LLM_MODEL=claude-haiku-4-5
   
   # Whisper Configuration
   WHISPER_MODEL=small.en
   WHISPER_DEVICE=auto
   WHISPER_COMPUTE_TYPE=auto
   ASR_CHUNK_SECONDS=3.0
   
   # CORS - Update with your Vercel dashboard URL
   CORS_ORIGINS=https://larpchekr-dashboard-xxx.vercel.app,http://localhost:3000
   
   # Email
   MAGIC_LINK_FROM=noreply@larpchekr.app
   RESEND_API_KEY=
   
   # GitHub OAuth (optional)
   GITHUB_OAUTH_CLIENT_ID=
   GITHUB_OAUTH_CLIENT_SECRET=
   GITHUB_OAUTH_REDIRECT_URL=
   
   # Storage
   STORAGE_BACKEND=local
   
   # LinkedIn (optional)
   LINKEDIN_EMAIL=
   LINKEDIN_PASSWORD=
   LINKEDIN_COOKIE=
   ```

6. **Deploy**:
   - Click "Deploy" button
   - Railway will:
     - Install dependencies from `requirements.txt`
     - Run the Procfile command
     - Expose your service on a public URL

7. **Get Your Backend URL**:
   - In Railway dashboard, go to "Settings" → "Domains"
   - Copy your generated domain (looks like: `larpchekr-backend-prod.up.railway.app`)

8. **Update Vercel Dashboard**:
   - Go to Vercel project settings
   - Update `NEXT_PUBLIC_API_BASE` to your Railway URL
   - Vercel will automatically rebuild and redeploy

## Monitoring

- **Logs**: Click "Deployments" tab in Railway to see build and runtime logs
- **Metrics**: "Monitoring" tab shows CPU, memory, network usage
- **Alerts**: Set up notifications for failures

## Troubleshooting

### MongoDB Connection Error
- Check `MONGO_URL` is correctly set in Variables
- Make sure it's the full connection string including password

### Port Error
- Railway automatically assigns `$PORT` environment variable
- Procfile command must use `--port $PORT`

### Dependencies Not Installing
- Check `backend/requirements.txt` exists
- Railway will auto-detect and install Python dependencies

### Deployment Fails
- Click "Deployments" → view logs
- Common issues: invalid env vars, missing dependencies
- Fix and push to GitHub - Railway auto-redeploys

## Cost

- **Free tier**: Good for small deployments
  - 500 CPU hours/month
  - 5GB memory/month
  - Free shared PostgreSQL/MongoDB with projects
- **After free tier**: Pay-as-you-go (~$5-10/month for typical hackathon project)

## Next Steps

1. Deploy to Railway (this guide)
2. Deploy Dashboard to Vercel (see VERCEL_DEPLOYMENT.md)
3. Test API connectivity
4. Users can now provide their own LLM keys via Settings page
