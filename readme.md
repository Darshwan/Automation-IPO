# Automation IPO (MVP)

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
- Keep credential values in local environment variables and do not commit them.

## Next Milestones

1. Harden browser selectors against UI changes and add richer extraction mapping.
2. Add guarded final submit controls with explicit confirmation gates.
3. Expand notifier providers (Twilio/SendGrid) and retry behavior.
4. Add backend API and persistent database storage.
5. Add CI with GitHub Actions.

## Compliance Reminder

Review MeroShare terms and local regulations before enabling any live automation.
