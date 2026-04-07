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
- Pluggable `MeroShareClient` interface with mock and HTTP-based providers
- IPO detection service with local state persistence
- Console notifier
- Unit tests for detection/state behavior
- Email notifier support behind config-driven selection

## Next Milestones

1. Add browser automation (Playwright/Selenium) for real MeroShare login + IPO fetch.
2. Expand the HTTP client with the live MeroShare request flow and guardrails.
3. Add apply-flow automation with retries and explicit safety controls.
4. Add Twilio/SendGrid notifier providers and expand delivery options.
5. Add backend API and persistent database storage.
6. Add CI with GitHub Actions.

## Compliance Reminder

Review MeroShare terms and local regulations before enabling any live automation.
