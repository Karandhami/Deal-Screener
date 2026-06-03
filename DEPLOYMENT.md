# Deployment Guide — getting a live URL

Your app has two halves that both go live:

- **Backend** (FastAPI engine) → Render.com
- **Frontend** (React dashboard) → Vercel

Do them in this order: GitHub → Render → Vercel.

---

## Stage 1 — Push to GitHub

From the project root (`deal-screener/`), in a terminal:

```bash
git init
git add .
git commit -m "Initial commit: deal screening engine"
```

Then on github.com:
1. Click the **+** (top right) → **New repository**.
2. Name it `deal-screener`. Leave it **empty** (no README, no .gitignore — you already have them). Click **Create**.
3. GitHub shows you commands under "…or push an existing repository." Copy the two lines that look like:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/deal-screener.git
   git branch -M main
   git push -u origin main
   ```
4. Run them. Refresh the GitHub page — your code is now up.

---

## Stage 2 — Deploy the backend to Render

1. Go to **render.com**, sign up / log in **with your GitHub account**.
2. Dashboard → **New +** → **Web Service**.
3. Connect your `deal-screener` repo (authorise Render to see it if asked).
4. Render should auto-detect the settings from `render.yaml`. If it asks
   manually, use:
   - **Runtime:** Python 3
   - **Build command:** `pip install -e ".[api]"`
   - **Start command:** `uvicorn dealscreener.api.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Click **Create Web Service**. First build takes 3–5 minutes.
6. When it's live you'll get a URL like
   `https://deal-screener-api.onrender.com`. **Copy it.**
7. Test it: open `<that URL>/api/health` in your browser → should show
   `{"status":"ok"}`.

> Free tier sleeps after ~15 min idle; the first request after that takes
> 30–50s to wake. Normal for a portfolio demo.

---

## Stage 3 — Deploy the frontend to Vercel

1. Go to **vercel.com**, sign up / log in **with GitHub**.
2. **Add New… → Project** → import your `deal-screener` repo.
3. **Important — set the Root Directory to `frontend`** (click *Edit* next to
   Root Directory and choose the `frontend` folder). Vercel then auto-detects
   Vite.
4. Expand **Environment Variables** and add one:
   - **Name:** `VITE_API_URL`
   - **Value:** your Render URL from Stage 2 (e.g.
     `https://deal-screener-api.onrender.com`) — no trailing slash.
5. Click **Deploy**. ~1–2 minutes.
6. You get a live URL like `https://deal-screener.vercel.app`. **This is the
   one you share.**

---

## Stage 4 — Lock down CORS (recommended)

Right now the backend accepts requests from anywhere. To restrict it to your
frontend:

1. In **Render** → your service → **Environment** → add a variable:
   - **Key:** `ALLOWED_ORIGINS`
   - **Value:** your Vercel URL (e.g. `https://deal-screener.vercel.app`)
2. Render redeploys automatically. Done.

---

## If something doesn't work

- **Dashboard loads but "Cannot reach the API"** → the `VITE_API_URL` in
  Vercel is wrong or missing, or the Render service is asleep (wait 50s and
  retry).
- **Render build fails** → check the build log; usually a Python version
  mismatch. `render.yaml` pins 3.11.9.
- **SEC Live returns nothing on the deployed version** → some free hosts rate
  limit outbound requests; the Sample and Upload modes always work.
