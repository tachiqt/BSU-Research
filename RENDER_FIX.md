# Fix Render Deployment Error

## Problem
```
ModuleNotFoundError: No module named 'your_application'
==> Running 'gunicorn your_application.wsgi'
```

## Solution

Render is using the wrong start command. You need to update it in your Render dashboard.

---

## Step-by-Step Fix

### 1. Go to Your Render Dashboard
- Navigate to your Web Service
- Click on **"Settings"** tab (left sidebar)

### 2. Update Start Command
Find the **"Start Command"** field and change it to:

```
gunicorn app:app --bind 0.0.0.0:$PORT
```

**Important**: Make sure it's exactly `app:app` (not `your_application.wsgi`)

### 3. Verify Other Settings

Make sure these settings are correct:

| Setting | Value |
|---------|-------|
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT` |

### 4. Save and Redeploy
- Click **"Save Changes"**
- Render will automatically redeploy
- Or manually trigger a deploy from the **"Manual Deploy"** tab

---

## Alternative: Use Procfile

If you prefer, you can create/update the `Procfile` in the `backend` directory:

**File**: `backend/Procfile`
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

Then in Render:
- Leave **Start Command** empty (Render will use Procfile automatically)
- Or set it to: `gunicorn app:app --bind 0.0.0.0:$PORT`

---

## Quick Checklist

- [ ] Root Directory = `backend`
- [ ] Build Command = `pip install -r requirements.txt`
- [ ] Start Command = `gunicorn app:app --bind 0.0.0.0:$PORT`
- [ ] Environment Variables set (SCOPUS_API_KEY)
- [ ] Save changes

---

## Why This Happens

Render sometimes auto-detects Django projects and uses `your_application.wsgi` as the default start command. Since this is a Flask app, we need to explicitly tell it to use `app:app` where:
- `app` = the Python file (`app.py`)
- `app` = the Flask instance variable (`app = Flask(__name__)`)

---

## Still Having Issues?

1. Check **Logs** tab for detailed error messages
2. Verify `backend/app.py` exists and contains `app = Flask(__name__)`
3. Ensure `backend/requirements.txt` includes `gunicorn`
4. Try manual deploy from **Manual Deploy** tab
