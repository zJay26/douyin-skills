# Changelog

All notable changes are documented here. Releases follow semantic versioning, and each stable tag has detailed notes under [`docs/releases/`](./docs/releases/).

## [1.1.0] - 2026-08-14

### Added

- An explicit `PlatformAdapter` contract for platform identity, public URLs, content-reference parsing, navigation entry points, selectors, and text markers.
- The first `DouyinAdapter` implementation with focused injection tests for shared workflows.

### Changed

- Routed platform-specific browser details through the adapter while keeping the shared browser lifecycle, safety policy, result certainty, and JSON CLI contract unchanged.
- Preserved the legacy `douyin.urls` and `douyin.selectors` exports as compatibility wrappers.

### Documentation

- Documented the reusable adapter boundary and marked the corresponding roadmap item complete without adding or claiming a second platform.

## [1.0.1] - 2026-08-12

### Added

- Eleven versioned, synthetic page-state fixtures for login, risk, search, detail, and photo-publishing decisions.
- Shared production classifiers with schema, expected-result, canonical-URL, and privacy validation.
- Regression tests and Windows/Ubuntu CI coverage for fixture-to-runtime certainty semantics.

### Documentation

- A fixture-authoring and redaction guide that prohibits account, session, profile, and private-content data.
- v1.0.1 validation evidence and known limitations without treating synthetic fixtures as live-page proof.

## [1.0.0] - 2026-08-11

### Added

- Five composable Agent Skills for guarded Douyin environment, authentication, discovery, photo-publishing, and interaction workflows.
- A local-first JSON CLI with loopback-only Chrome CDP control and named profiles.
- Explicit human checkpoints and separate confirmed/unconfirmed result states.
- English-first and Chinese documentation, Agent ecosystem notes, contribution templates, and cross-platform CI.
- A reproducible, privacy-safe 40-second Demo GIF generated from synthetic data.
- Formal validation boundaries, release notes, and checksum-verifiable release packaging.

### Safety boundaries

- Publishing requires validation and a separate explicit confirmation.
- Captcha, identity checks, and platform risk controls are never bypassed.
- Unconfirmed irreversible actions are never reported as confirmed or retried automatically.

[1.1.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.1.0
[1.0.1]: https://github.com/zJay26/douyin-skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.0.0
