# Automation IPO (MVP)

## Legal Disclaimer

This project is for educational and controlled testing purposes. Automating actions against third-party financial systems may violate platform Terms of Service, trigger account restrictions, or create legal exposure depending on jurisdiction. You are responsible for confirming compliance before any live usage.

Live IPO submission is intentionally guarded by explicit environment flags and confirmation phrases. Do not enable live mode unless you have reviewed applicable Terms, regulations, and risk controls.

This project starts with a safe MVP pipeline:

- Detect new IPO entries from a provider
- Keep local state to avoid duplicate actions
- Trigger notifications for newly detected IPOs
- Expose extension points for real MeroShare automation and application submission

## Quick Start

1. Create a virtual environment and activate it.
2. Install dependencies:
   - `pip install -e ".[dev]"`
3. Copy environment template:
   - `copy .env.example .env`
4. Run the watcher:
   - `automation-ipo --once`
   - or `python -m automation_ipo.main --once`

## Run Tests

- `pytest -q`

## Current Scope

The current implementation includes:

- Config loading from environment
- Pluggable `MeroShareClient` interface with mock, HTTP, and browser providers
- IPO detection service with local state persistence
- Console notifier
- Unit tests for detection/state behavior
- Email notifier support behind config-driven selection
- Browser login and ASBA listing scaffold with dry-run safety for apply flow

## Security First Defaults

- Browser mode requires Depository Participant, username, password, and TOTP secret.
- Apply automation is disabled by default.
- Dry-run is enabled by default for browser apply form preparation.
- Live submission requires exact `MEROSHARE_LIVE_APPLY_CONFIRMATION` phrase and form secrets.
- Live submission also requires `MEROSHARE_LEGAL_ACKNOWLEDGED=true`.
- Keep credential values in local environment variables and do not commit them.

## Runtime Warning Banner

At startup, the application prints legal and safety warnings indicating whether it is in safe mode or live-apply mode.

## Next Milestones

1. Harden browser selectors against UI changes and add richer extraction mapping.
2. Add guarded final submit controls with explicit confirmation gates.
3. Expand notifier providers (Twilio/SendGrid) and retry behavior.
4. Add backend API and persistent database storage.
5. Add CI with GitHub Actions.

## Compliance Reminder

Review MeroShare terms and local regulations before enabling any live automation.
