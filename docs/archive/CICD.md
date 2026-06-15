# CI/CD Pipeline Documentation

**Pipeline:** GitHub Actions → Test → Security Scan → Deploy to Render

---

## Workflow Overview

```
Push to main:
  ├── Test Suite (pytest)
  ├── Security Audit (pip-audit, bandit)
  ├── Build (pip install, uvicorn)
  └── Deploy (Render)
```

---

## GitHub Actions Workflows

### 1. Test & Deploy Pipeline (`.github/workflows/test-and-deploy.yml`)

**Triggers:**
- Push to `main`
- Pull requests to `main`

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Install dependencies
4. Run security scans (pip-audit, bandit)
5. Run test suite (pytest)
6. Deploy to Render (on main branch only)

---

## Configuration

### Render Environment Variables
Set in Render Dashboard → Environment:

```env
YOUTUBE_CLIENT_ID=343644756734-vht75phpm5ae7m3dm439aolurvpuhdc1.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=<from Google Cloud Console>
DATABASE_URL=<Render PostgreSQL URL>
```

### GitHub Secrets
Set in GitHub → Settings → Secrets and variables → Actions:

```env
RENDER_API_KEY=<from Render Dashboard>
```

---

## Pipeline Steps

### 1. Test Job
- Run pytest with coverage
- Report test results
- Fail if coverage < 80%

### 2. Security Job
- Scan dependencies for CVEs
- Run static analysis (bandit)
- Check for hardcoded secrets

### 3. Deploy Job
- Trigger Render deployment
- Monitor deploy status
- Run post-deploy health checks

---

## Monitoring

### GitHub Actions Dashboard
View pipeline status at: `https://github.com/dave-patrick/tube-manager/actions`

### Render Dashboard
View deployment status at: `https://dashboard.render.com`

### Health Check
After deployment, verify: `https://tubemanager.onrender.com/health`

---

## Rollback

If a deployment fails:
1. **GitHub Actions** - Auto-rolls back to stable commit
2. **Render** - Manual rollback from dashboard
3. **Database** - Automatic daily backups (to be configured)

---

## Scheduled Maintenance

Add to gitignore:
- `.env`
- `*.env`
- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `*.sqlite3`

---

## Next Steps

1. Create GitHub Actions workflows
2. Configure Render environment variables
3. Add deployment scripts
4. Set up monitoring/alerting