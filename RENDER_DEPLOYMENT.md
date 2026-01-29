# Render Deployment Guide - BSU Research Dashboard

This guide provides step-by-step instructions for deploying the BSU Research Dashboard on Render.

---

## Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com) (free tier available)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **Scopus API Key**: Get from [dev.elsevier.com](https://dev.elsevier.com/)

---

## Step-by-Step Deployment

### Step 1: Create New Web Service

1. Log in to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository (or GitLab/Bitbucket)
4. Select your repository: `BSU-Research` (or your repo name)

### Step 2: Configure Build Settings

Fill in the following settings:

| Setting | Value |
|---------|-------|
| **Name** | `bsu-research-dashboard` (or your preferred name) |
| **Region** | Choose closest to your users (e.g., Singapore, US East) |
| **Branch** | `main` (or `master`) |
| **Root Directory** | `backend` ⚠️ **IMPORTANT** |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT` ⚠️ **MUST BE EXACT** |

**⚠️ CRITICAL**: The Start Command must be exactly `gunicorn app:app --bind 0.0.0.0:$PORT`
- Do NOT use `your_application.wsgi` (that's for Django)
- Do NOT use `app.wsgi` (that's for Django)
- Use `app:app` (Flask format: `module:variable`)
| **Auto-Deploy** | Yes (or No if you want manual deploys) |

### Step 3: Set Environment Variables

Click **"Advanced"** → **"Add Environment Variable"** and add these:

#### Required Environment Variables

| Key | Value | Description |
|-----|-------|-------------|
| `SCOPUS_API_KEY` | `your_scopus_api_key_here` | **REQUIRED** - Your Scopus API key from dev.elsevier.com |

#### Optional Environment Variables

| Key | Value | Description |
|-----|-------|-------------|
| `FLASK_ENV` | `production` | Set to `production` for production deployment (disables debug mode) |
| `PYTHON_VERSION` | `3.11.0` | Python version (optional, Render auto-detects) |

**Note**: Render automatically provides the `PORT` environment variable, so you don't need to set it manually.

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies from `backend/requirements.txt`
   - Start the application with Gunicorn
3. Wait for deployment to complete (usually 2-5 minutes)

### Step 5: Access Your Application

Once deployed, your app will be available at:
```
https://your-app-name.onrender.com
```

Render provides a free HTTPS certificate automatically.

---

## Environment Variables Summary

### Minimum Required (Must Have)

```env
SCOPUS_API_KEY=abf390ccc8511e779226d684ddf08a8b
```

**Replace with your actual Scopus API key!**

### Recommended for Production

```env
SCOPUS_API_KEY=your_scopus_api_key_here
FLASK_ENV=production
```

### Complete Example (All Variables)

```env
SCOPUS_API_KEY=abf390ccc8511e779226d684ddf08a8b
FLASK_ENV=production
PYTHON_VERSION=3.11.0
```

---

## How to Add Environment Variables in Render

### Method 1: During Service Creation

1. In the "New Web Service" form
2. Scroll to **"Advanced"** section
3. Click **"Add Environment Variable"**
4. Enter key and value
5. Click **"Add"**
6. Repeat for each variable

### Method 2: After Service Creation

1. Go to your service dashboard
2. Click **"Environment"** tab (left sidebar)
3. Click **"Add Environment Variable"**
4. Enter key and value
5. Click **"Save Changes"**
6. Render will automatically redeploy

---

## Render-Specific Notes

### Automatic HTTPS
- Render provides free SSL certificates automatically
- Your app is accessible via `https://` immediately

### Port Configuration
- Render automatically sets the `PORT` environment variable
- The start command uses `$PORT` to bind to the correct port
- **Do NOT** set `PORT` manually in environment variables

### Free Tier Limitations
- **Spins down after 15 minutes of inactivity** (free tier)
- First request after spin-down may take 30-60 seconds
- Upgrade to paid plan for always-on service

### Database Persistence
- The SQLite database (`faculty.db`) is stored in the filesystem
- **Important**: On free tier, data may be lost if the service is redeployed
- Consider using Render PostgreSQL (paid) or external database for production

### Build Logs
- View build logs in the Render dashboard
- Check for any errors during dependency installation
- Common issues: missing dependencies in `requirements.txt`

---

## Troubleshooting

### Issue: "Module not found" errors

**Solution**: Ensure all dependencies are in `backend/requirements.txt`:
```txt
Flask>=3.0.0
Flask-CORS>=4.0.0
requests>=2.31.0
python-dotenv>=1.0.0
pandas>=2.0.0
openpyxl>=3.1.0
gunicorn>=21.2.0
```

### Issue: "SCOPUS_API_KEY not found"

**Solution**: 
1. Go to Environment tab
2. Verify `SCOPUS_API_KEY` is set correctly
3. Check for typos (no spaces, correct key)
4. Redeploy after adding/updating

### Issue: App shows "Application Error"

**Solution**:
1. Check **Logs** tab in Render dashboard
2. Look for Python errors or import errors
3. Verify `Root Directory` is set to `backend`
4. Verify `Start Command` is correct: `gunicorn app:app --bind 0.0.0.0:$PORT`

### Issue: Static files not loading

**Solution**: 
- The Flask app serves static files automatically
- Ensure frontend files (index.html, style.css, etc.) are in the repository root
- Check that the app is serving from the correct directory

### Issue: Database not persisting

**Solution**:
- Free tier: Data may reset on redeploy
- Use Render PostgreSQL (paid) or external database
- Or use the Excel upload feature to re-import data

---

## Updating Your Deployment

### Update Code
1. Push changes to your GitHub repository
2. Render automatically detects changes
3. Triggers a new deployment
4. Monitor deployment in the dashboard

### Update Environment Variables
1. Go to **Environment** tab
2. Edit or add variables
3. Click **"Save Changes"**
4. Render redeploys automatically

### Manual Redeploy
1. Go to **Manual Deploy** tab
2. Click **"Deploy latest commit"**
3. Or deploy a specific branch/commit

---

## Quick Reference

### Render Dashboard URLs
- **Dashboard**: https://dashboard.render.com
- **Your Service**: https://dashboard.render.com/web/your-service-name
- **Logs**: Available in the service dashboard

### Important Files for Render
- `backend/requirements.txt` - Dependencies
- `backend/app.py` - Main application
- `Procfile` (optional) - Can be used instead of start command
- Root directory must be set to `backend`

### Start Command
```
gunicorn app:app --bind 0.0.0.0:$PORT
```

### Build Command
```
pip install -r requirements.txt
```

---

## Environment Variables Checklist

Before deploying, ensure you have:

- [ ] `SCOPUS_API_KEY` - Your Scopus API key (REQUIRED)
- [ ] `FLASK_ENV=production` - For production mode (RECOMMENDED)
- [ ] `PORT` - **DO NOT SET** - Render provides this automatically

---

## Support

- **Render Docs**: https://render.com/docs
- **Render Support**: Available in dashboard
- **Application Logs**: Check in Render dashboard for errors

---

**Last Updated**: January 2026
