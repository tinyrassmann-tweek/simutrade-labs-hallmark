# SimuTrade Labs project guidance

- Read README.md, START-HERE.html, and design.md before making changes.
- All balances, positions, orders, and results use simulated funds. No broker execution or real-money trading.
- Preserve the original logo and the navy/cyan/gold brand palette.
- Keep the data source clearly labeled. The included feed is synthetic; provider data requires configured credentials and entitlements.
- Stop and target inputs are planning references, not automatic execution orders in this build.
- The Python application has no third-party runtime dependencies. Start with python3 server.py.
- Verify changes with python3 -m unittest discover -s tests -v and JavaScript syntax checks when applicable.
- Keep public assets in public/assets. Keep credentials in server environment variables.
- Never commit data/, .env, real tokens, account records, or session records.
- Keep implementation limitations in the launch guide accurate; do not present templates, unsent follow-up drafts, or unconfigured integrations as live services.
