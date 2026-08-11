# Changelog

All notable changes are documented here. Releases follow semantic versioning, and each stable tag has detailed notes under [`docs/releases/`](./docs/releases/).

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

[1.0.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.0.0
