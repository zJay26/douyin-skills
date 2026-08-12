# Roadmap

This roadmap separates implemented behavior from evidence we still need. Dates are intentionally omitted: reliability gates matter more than optimistic deadlines.

## Principles

- Keep account sessions and browser control local by default.
- Treat human verification as a supported state, not a failure to bypass.
- Separate confirmed outcomes from clicks and assumptions.
- Stabilize the shared contract before adding another platform.
- Prefer real fixtures, tests, and manual validation notes over broad compatibility badges.

## Current baseline

- [x] Five composable Douyin Skills for environment, authentication, discovery, photo publishing, and basic interactions
- [x] Structured JSON CLI and loopback-only Chrome CDP runtime
- [x] Named local profiles and default-account handling
- [x] Explicit publish validation and confirmation
- [x] Unit tests on Windows and Ubuntu CI
- [x] English-first repository documentation with a complete Chinese guide

The baseline does **not** prove arbitrary page-version compatibility or authenticated publishing on every account.

## Next: strengthen the Douyin foundation

- [x] Add sanitized selector and page-state fixtures for login, risk, search, detail, and publishing flows
- [x] Publish a repeatable manual validation checklist with Chrome and page-version notes
- [x] Add a synthetic, privacy-safe demo of the end-to-end agent workflow
- [x] Define a release and changelog cadence so users can distinguish stable behavior from ongoing work
- [ ] Turn common page-drift reports into focused regression tests

## Then: extract the reusable contract

- [x] Document a stable cross-command result envelope for confirmed, failed, blocked, and unconfirmed outcomes
- [ ] Isolate platform URLs, selectors, and page flows behind an explicit adapter boundary
- [ ] Keep browser lifecycle, profiles, timeouts, and human checkpoints platform-neutral
- [ ] Add an integration smoke test for at least one Agent Skills client beyond the primary OpenClaw path
- [ ] Evaluate additional tool surfaces only when they can reuse the same execution core

## Later: evidence-led ecosystem expansion

- [ ] Publish a small adapter-authoring guide with safety and validation requirements
- [ ] Evaluate one additional social or creator platform with an authorized manual test environment
- [ ] Add that adapter only if it can preserve local execution, explicit authority, and honest result states
- [ ] Compare client and platform integrations using the same fixtures and reporting vocabulary

No additional platform is selected or promised today.

## Not on the roadmap

- captcha, identity-check, or risk-control bypasses;
- account farming, engagement inflation, or spam-oriented bulk actions;
- silent retries of irreversible actions;
- claims of compatibility without a repeatable validation path.

## Community input

Use [Discussions](https://github.com/zJay26/douyin-skills/discussions) for workflow ideas, client-integration notes, and platform-adapter proposals. Use [Issues](https://github.com/zJay26/douyin-skills/issues) when the work is scoped and testable.
