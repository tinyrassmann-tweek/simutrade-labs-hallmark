# SimuTrade Labs

Premium consumer landing page and functional simulated-trading education app. Visual edition 1.1, November 17, 2026. This repository is the shared source for the project, including the site, app, original brand assets, operator tools, tests, deployment files, and downloadable build.

## Run locally

```bash
python3 server.py
```

Open http://localhost:3000 for the site and http://localhost:3000/app for the app. Python 3.12+ is required. No pip or npm dependencies are required for the app runtime.

```bash
python3 -m unittest discover -s tests -v
```

## Build the downloadable package

```bash
python3 build_release.py
```

Generated previews and the complete ZIP appear in `dist/`. They are reproducible outputs rather than committed duplicate bundles. All modular source and original assets are included. The standalone landing embeds the app and legal previews. Guest practice works in the preview; account and lead APIs require running the Python server.

## Key files

| Path | Purpose |
| --- | --- |
| `public/index.html` | Landing page |
| `public/app.html` and `public/app.js` | Trader and operator workspace |
| `public/style.css`, `public/premium.css`, `public/tokens.css`, `public/base.css` | Shared styling, visual edition, and design tokens |
| `public/assets/` | Supplied logo and custom illustrative photographs |
| `server.py` | Backend and web server |
| `tests/` | Backend regression tests |
| `build_release.py` | Generates standalone HTML previews, launch guide, and complete ZIP in `dist/` |
| `START-HERE.html` | Full launch and capability guide |
| `.hallmark/` | Original page snapshots, design audit, verification record, and source comparison diff |
| `requirements/` | Original operating-system requirements and landing prompt |
| `deploy-google-cloud.sh` and `Dockerfile` | Google Cloud deployment package |

## Agent handoff

Work from this repository. Preserve the simulated-funds-only posture and existing branding. Read `design.md`, `START-HERE.html`, and `AGENTS.md` before changing the UI. Run the tests before pushing. Never commit local databases, real credentials, or generated session data.

Public source access does not mean the app has been deployed as a live service. Google Cloud publishing and optional provider integrations still require project access and configuration.

## Persistence
Local: SQLite at `data/simutrade.db`. Keep this directory private and back it up. Cloud Run: Firestore Native via the runtime identity. Never use SQLite for Cloud Run production because its filesystem is ephemeral. Cloud Run without GOOGLE_CLOUD_PROJECT fails fast.

Guest records stay in localStorage. Account data is separate. No automatic guest import.
Server calculates authenticated trade fills, risk checks, and realized P&L. Workspace writes cannot set balances, positions, or trade history. Version preconditions prevent stale concurrent overwrites.

## Scope
Synthetic replay included; Twelve Data quotes optional. Manual entries/exits only; stops/targets are references, not auto orders. Fixed balance-based challenge limits; no trailing drawdown/equity enforcement. Rules coach included; Gemini optional. CRM, editable drafts, and unsent follow-up plans included; no email delivery, outside CRM sync, booking, paid plans, or background jobs.

No email verification or password recovery yet. Owner waitlist inbox requires both ADMIN_EMAIL and a separate ADMIN_ACCESS_TOKEN. Secrets never go into static files. No claims that results predict live trading or qualification.

Cloud deployment, Firestore, Gemini, and provider credentials have not been exercised against a connected account in this build session. The deployment script is supplied, not executed. Public launch needs operator contact details and identity verification/recovery configured.

## Visual edition 1.1

The landing explains the practice loop through a risk check, controlled synthetic replay, reflection preview, geometric sizing calculator, and voluntary pause. Demo results are labeled examples. The app retains its real routes, storage, and simulation logic, with a new visual treatment and linked session guidance. No front-end framework, external fonts, or animation library is required.

See `verification/visual-edition.json` for the checks performed in this update. Historical `.hallmark/` records describe the earlier foundation.
