# Changelog

All notable changes are documented here. Releases follow semantic versioning, and each stable tag has detailed notes under [`docs/releases/`](./docs/releases/).

## [Unreleased]

## [1.3.0] - 2026-08-23

### Added

- Added a bounded `comment-video` workflow that fills and sends one public
  comment only when the page exposes recognizable controls, with explicit
  confirmed, unconfirmed, and unavailable states.
- Added platform-owned favorite and comment control selectors for current
  Douyin video pages.
- Added native CDP text insertion for controlled editors such as the current
  DraftJS comment composer.

### Fixed

- Rechecked transient verification interstitials after navigation so an
  already-authenticated Chrome session is not paused before its page settles;
  persistent risk pages still require manual verification.
- Added DOM state confirmation and a read-only `get-interaction-state` command
  for like/favorite controls; active toggles are not clicked again.
- Preserved existing comment drafts, required a newly observed matching comment
  for confirmation, and avoided treating arbitrary editable elements as the
  comment composer.
- Repaired current hot-list extraction by prioritizing the semantic right-list
  container and validating the generated JavaScript syntax.
- Accepted the current Creator Center photo-post route, waited for a positive
  upload-ready marker, and rejected title/body values that the page truncated
  or rewrote.
- Restricted music selection to semantic song-name and enabled “使用” controls,
  avoiding generic panel buttons and returning the applied song name.

## [1.2.0] - 2026-08-21

### Added

- Exposed `get-trending-topics` for bounded public topic discovery with
  explicit `page_drift` reporting.
- Added synthetic trending-topic fixtures for ready, risk, and page-drift
  states.

### Fixed

- Reused an existing local Chrome debugging session instead of restarting it
  solely to match the default headless preference.
- Fell back to a public content description when a detail page has no usable
  document title, and waited for transient detail loading markers before
  classifying the result.
- Reported a clear `wrong_page` state when publish validation runs outside the
  creator upload page.

## [1.1.2] - 2026-08-18

### Added

- Focused page-state regression validation with `--flow` and `--fixture-id`
  filters for reproducing a reported page-drift boundary.
- Synthetic detail fixtures for verification-risk and unavailable-content states,
  alongside the existing route-drift fixture.

### Changed

- Marked the roadmap item for turning common page-drift reports into focused
  regression tests complete.
- Documented focused fixture validation in the English and Chinese development
  guides.

## [1.1.1] - 2026-08-18

### Added

- A maintainer-facing [Adapter authoring guide](./docs/ADAPTER_AUTHORING.md)
  covering the `PlatformAdapter` contract, selector ownership, safety gates,
  privacy-safe evidence, and automated/manual validation.
- A documentation contract test that keeps the guide connected to the
  authoritative adapter, result, validation, and contribution references.

### Documentation

- Marked the adapter-authoring roadmap item complete without adding another
  platform or changing the runtime/result contract.

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

[1.3.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.3.0
[1.2.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.2.0
[1.1.2]: https://github.com/zJay26/douyin-skills/releases/tag/v1.1.2
[1.1.1]: https://github.com/zJay26/douyin-skills/releases/tag/v1.1.1
[1.1.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.1.0
[1.0.1]: https://github.com/zJay26/douyin-skills/releases/tag/v1.0.1
[1.0.0]: https://github.com/zJay26/douyin-skills/releases/tag/v1.0.0
