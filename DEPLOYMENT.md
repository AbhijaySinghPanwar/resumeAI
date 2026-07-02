# ResumeAI v1.0 Deployment Guide

This guide covers deploying ResumeAI v1.0 on Render using Neon PostgreSQL.

## Prerequisites
- A Render account (Free Tier supported).
- A Neon PostgreSQL database.
- A Gemini API Key.
- Optional: A custom domain for the frontend.

## Step 1: Database Setup
1. Create a project in [Neon](https://neon.tech/).
2. Copy the connection string. Ensure it uses the pooled connection string if available, though SQLAlchemy is configured to use pooling locally via `engine.py`.
3. Format: `postgresql://[user]:[password]@[endpoint]/[dbname]?sslmode=require`

## Step 2: Render Web Service Setup
1. Connect your GitHub repository to Render.
2. Select **New Web Service**.
3. **Runtime:** Docker.
4. **Build Command:** (Handled automatically by Dockerfile).
5. **Start Command:** (Handled automatically by Dockerfile).

## Step 3: Environment Variables
Configure the following Environment Variables in the Render dashboard:

| Variable | Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production security mode. |
| `SECRET_KEY` | `your_64_char_hex_string` | Run `python -c "import secrets; print(secrets.token_hex(32))"` locally to generate. |
| `DATABASE_URL` | `postgresql://...` | Your Neon database string. |
| `GEMINI_API_KEY` | `AIza...` | Your Gemini API Key. |
| `ALLOWED_ORIGINS`| `["https://your-domain.com"]` | Array of permitted frontend domains. |
| `EMBEDDING_ENGINE` | `onnx` | Uses ONNX Runtime for low-memory semantic matching. |

## Step 4: Health Monitoring
Render will use the Dockerfile's `HEALTHCHECK` directive automatically, but you can also configure Render's custom health check path:
- **Path:** `/api/health`

## Step 5: Post-Deployment Verification
Once deployed, verify the deployment:
1. Check Health: `curl https://your-app.onrender.com/api/health`
2. Check Version: `curl https://your-app.onrender.com/api/version`
3. Try uploading a PDF from the frontend to ensure database auto-saves function correctly.

## Rollback Procedures
If ONNX embedding fails or causes unexpected matching degradation, you can revert to the PyTorch engine by changing the environment variable `EMBEDDING_ENGINE=pytorch`. Warning: This may exceed the 512MB RAM limit on Render's Free Tier.
