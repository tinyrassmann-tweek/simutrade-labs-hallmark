# SimuTrade Labs — Visual edition 1.1

Updated November 17, 2026.

The complete modular source is included: premium landing page, simulated-trading practice app, operator portals, original logo, custom illustrative photography, Python backend, 13 regression tests, portable HTML builder, Dockerfile, and Google Cloud deployment script.

Run `python3 server.py` and open http://localhost:3000. Generate the standalone previews and full ZIP with `python3 build_release.py`.

The landing explains the consumer benefit through working, labeled practice examples. Guest access needs no account or deposit. All balances and trades are simulated. The included feed is synthetic. Optional providers and AI generation require configuration.

Validation: 13 backend tests pass, both application JavaScript files parse, and browser checks cover the risk/replay/reflection previews, durable lead saving, simulated entry/manual exit, journal saving, and responsive navigation. See `verification/visual-edition.json`.

Google Cloud deployment, a custom domain, and external provider integrations are not verified as live. The source package is deployable; it is not evidence of an active production service. No new paid services were provisioned in this update.

Historical Hallmark records are retained under `.hallmark/`. The earlier public landing draft is preserved under `requirements/Previous-Public-Landing-2026-11-09.html`; the current site source is `public/index.html`.
