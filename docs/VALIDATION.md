# Validation and support boundaries

This document records what the repository can demonstrate repeatably and what still requires a real user, account, and current web page. It is an evidence boundary, not a compatibility promise.

## What automated checks cover

The GitHub Actions matrix runs the same core checks on:

| Runner | Python | Node.js | Evidence produced |
| --- | --- | --- | --- |
| Windows | 3.13 | 24 | Python unit tests, Node.js bridge test, syntax checks |
| Ubuntu | 3.9 | 18 | Python unit tests, Node.js bridge test, syntax checks |
| Ubuntu | 3.13 | — | Ruff lint and format checks |

These checks exercise behavior that does not need a Douyin account:

- account configuration, safe profile names, port allocation, and corrupt-config handling;
- loopback-only Chrome launch arguments and browser discovery overrides;
- CLI argument validation, including explicit publish confirmation and search limits;
- Douyin URL normalization and rejection of off-domain content links;
- login-state classification with synthetic browser responses;
- image/video-path validation, exact title/body application, media-specific
  upload-ready evidence, video-cover validation, semantic music controls, and
  distinct confirmed/unconfirmed publish states;
- one-at-a-time interaction semantics that do not invent a final state,
  including existing-draft preservation and confirmed/unconfirmed comments;
- the Node.js CDP request/response bridge, including native text insertion;
- sanitized page-state fixtures for login, risk, search, detail, and publishing certainty, including schema and privacy rules plus focused flow/id reruns for page-drift reports.

The repository also includes a deterministic, synthetic 40-second walkthrough. Its source is [`assets/demo/index.html`](../assets/demo/index.html), and maintainers can render [`assets/demo.gif`](../assets/demo.gif) with:

```bash
npm run render:demo
```

The demo contains no real account, cookie, QR code, phone number, profile path, or user content. It makes no network requests. It validates the explanatory flow and presentation only; it is not a live Douyin test.

The versioned [page-state fixtures](../fixtures/page_states/README.md) are also synthetic. They exercise the same classifiers used by production command paths, but model only the minimum state needed for a decision. They contain no stored HTML, screenshot, browser profile, cookie value, or real user content. Passing fixture tests protects result semantics; it does not prove that selectors still extract those signals from today's live pages.

## Supported source scope

The current source tree implements the following Douyin web workflows through
the local CLI. The `v1.4.0` tag is the first stable release that includes the
guarded video-publishing workflow:

- environment diagnosis and named local-account configuration;
- login-state inspection, QR-code retrieval, and user-completed SMS verification;
- public video/note search and detail lookup;
- photo-post form filling and music selection, plus video upload, custom-cover
  setting, media-specific pre-publish validation, and separately confirmed
  publish clicks;
- one-at-a-time like, favorite, public-comment, and public-link sharing actions.

Support here means the command and its safety/result contract are implemented and tested with synthetic inputs. Live success still depends on the current page, account state, and platform controls.

## Manual acceptance checklist

Use this checklist when validating against a real account. Never attach the resulting profile, cookies, QR code, phone number, or private content to an Issue or Discussion.

1. Record the operating system, Chrome/Chromium version, date, and the command under test.
2. Run `python scripts/cli.py doctor` and retain only the non-sensitive summary.
3. Use a dedicated local profile and a low-risk test account that you are authorized to operate.
4. Confirm login and risk pages are surfaced for human completion rather than bypassed.
5. For discovery, compare the structured result with the visible public page.
6. For photo publishing, fill synthetic test content first and stop at `validate-publish`; for video publishing, stop at `validate-publish-video`.
7. If a real publish is necessary, inspect the visible page and provide `--confirm` separately.
8. Treat `publish_clicked_unconfirmed` as unresolved: check Creator Center and never blind-retry.
9. For comments, preserve any existing draft, submit once, and never retry
   `comment_clicked_unconfirmed`.
10. Record observed selectors or page-state changes without copying session data.

## Stable release gate

Every stable release requires all of the following on the tagged commit:

- the Windows and Ubuntu CI matrix is green;
- Ruff is green;
- the privacy-safe demo renders to a 30–45 second, 960×540 GIF;
- repository links, release documents, and English visual assets pass the repository integrity check;
- the source archive is reproducible and its SHA-256 checksum is published;
- the packaged CLI reports the expected project and result-contract versions.
- the page-state fixtures pass schema, expected-result, canonical-URL, and privacy validation.

## Not validated or guaranteed

The current source tree does **not** claim:

- successful login, search, interaction, or publishing for every account or current Douyin page version;
- captcha, identity-check, or risk-control automation or bypass;
- support for comment replies, direct messages, draft management, scheduling,
  or bulk operations;
- unattended or idempotent retry after an irreversible click;
- macOS runtime coverage in CI;
- plug-and-play execution on every Agent Skills client;
- compatibility with any social or creator platform other than the implemented Douyin adapter;
- long-term selector stability after Douyin changes its pages or policies.

Browser automation is inherently sensitive to page drift and platform controls. A passing CI run proves the repository's tested contracts; only a dated manual run can describe a particular account and page version.

## Reporting validation results

Use the repository's integration-report template for reproducible, non-sensitive findings. Security issues and any observation that would expose a session must follow [`SECURITY.md`](../SECURITY.md) instead of a public report.
