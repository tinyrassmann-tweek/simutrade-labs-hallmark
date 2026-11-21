# SimuTrade Labs

Live simulated trading education, private saved workspaces and seat-inclusive study teams.

Production: https://simutradelabs.thinktanksolutionsai.online/ · App: https://simutradelabs.thinktanksolutionsai.online/app

## Accepted production scope — November 20, 2026

All four requested closeout gates passed: actual customer CSV/JSON downloads and contents, mobile team workflows at 320px and 390px, real recovery-email delivery, and the existing director’s commercial handoff. The Mac operator performed both fictional activation and suspension with the portable helper. See `launch/2026-11-20/production-verification.json` and its HTML acceptance record.

The current runtime is `think-tank-hub-00009-zud`; Hosting version is `fceefb84a988b9e9`. The runtime image is unchanged from the patched image with zero reported vulnerability findings. Runtime source, later static corrections and acceptance records have distinct provenance in the ledger.

## Customer and commercial model

Free guest practice stays in the browser. Firebase email/password accounts save private work in Firestore. Each learner’s journal stays private; deliberately posted study notes are shared with the team. Founding Cohort is $19/month total for six monthly periods with five included seats. Optional Premium is $49/month total with ten included seats. The existing Think Tank Digital merchant processes payments. The existing operator verifies settled payment and the purchaser/team reference, confirms the founding cancellation schedule, and activates access within the published window. Read `public/cohort-terms.html` and `deployment/OPERATOR.md`.

Owner actions use `python3 deployment/simutrade_operator.py activate PRIVATE_FILE.json` (or `suspend`, or `team TEAM_ID`). The helper finds the existing Google Cloud CLI and trusted CA bundle on the Mac. Tokens stay private; the server checks the exact verified owner, Google issuer, configured audience and expiry. The old `deployment/operator.py` filename was removed to avoid shadowing Python’s standard library.

## Run locally

Python 3.12+ is required; the application uses the standard library.

```bash
python3 production.py
python3 -m unittest discover -s tests -v
python3 build_release.py
```

Open http://localhost:8080. SQLite is used only for local development. Local guest/account data is separate from production; Firebase recovery requires the configured production identity service. Cloud Run requires `GOOGLE_CLOUD_PROJECT` and durable Firestore. The hosted API prefix is `/api/simutrade/*`; the shared inquiry API is preserved.

Generated standalone previews and source ZIPs appear in `dist/`. They include the original assets and modular source. Standalone guest practice is a preview; server-backed accounts and commercial activation use the deployed service.

## Boundaries and source layout

All balances and execution are simulated. Included data is synthetic replay. Entries and exits are manual; reference stops and targets do not auto-execute. Fixed balance-based rules use UTC days and realized losses; trailing-equity and firm-specific qualification rules are not modeled. Coaching prompts are rules based. Optional licensed data and Gemini generation are not included as active services. CRM drafts and follow-up plans are unsent workspaces.

`public/` contains the landing, app, original logo and generated illustrative photographs. `production.py` provides hosted account/team operations; `server.py` supplies storage and simulation logic. `deployment/hub/` preserves the existing inquiry service with a namespaced proxy. `tests/` contains 21 backend regression tests. `.hallmark/` preserves historical design records. Read `AGENTS.md`, `design.md` and `START-HERE.html` before changing the UI. Never commit databases, real credentials, tokens or session data.
