# Adapter authoring guide

This guide is for maintainers who want to propose a platform adapter for the
shared local browser runtime. It explains the boundary, the evidence required
before a new adapter can be advertised, and the safety checks that must remain
true. It is an implementation and review checklist, not a compatibility
promise.

As of `v1.1.x`, this repository ships only the Douyin adapter. A new adapter
must bring its own authorized validation evidence; copying the Douyin selectors
or adding a name to a registry is not support.

## 1. Start with a scoped, authorized workflow

Write down the exact workflow before writing selectors:

- which public discovery, detail, interaction, or creator flow is in scope;
- which content kinds and URL forms are accepted;
- which actions require a human checkpoint or explicit confirmation;
- which pages, account states, browser versions, and operating systems will be
  validated;
- which behaviors are explicitly out of scope.

Use a dedicated account and local browser profile that you are authorized to
operate. Record sanitized page clues, not cookies, QR codes, phone numbers,
verification codes, browser profiles, private content, or full authenticated
HTML. A page-drift report should be reproducible without publishing someone
else's session data.

## 2. Keep the platform boundary narrow

The adapter owns platform facts. The shared runtime owns execution and safety
policy:

| Adapter-owned | Shared and must not be duplicated |
| --- | --- |
| Platform key, public hosts, URLs, content IDs, and content kinds | Chrome discovery, launch arguments, loopback-only CDP, profiles, and timeouts |
| Login, verification, risk, and inaccessible-page markers | Human checkpoints, CAPTCHA and risk-control stop rules |
| Search, detail, interaction, and creator-page selectors | JSON result envelope and confirmed/failed/blocked/unconfirmed semantics |
| Navigation entry points and positive result signals | Explicit publish confirmation and no-retry behavior for unknown outcomes |
| Platform content limits and policy-specific validation | CLI argument handling and shared error reporting |

Do not add a platform conditional to a shared workflow when the behavior is a
URL, selector, visible marker, or platform rule. Add it to the adapter and
cover the injected workflow instead. Do not turn a successful local page run
into a general compatibility claim.

## 3. Implement `PlatformAdapter`

The authoritative contract is [`scripts/platform_adapter.py`](../scripts/platform_adapter.py).
The complete Douyin reference implementation is
[`scripts/douyin/adapter.py`](../scripts/douyin/adapter.py). A new adapter
normally lives in `scripts/<platform>/adapter.py`, exposes a frozen default
instance, and uses `PlatformSelectors` for all browser-facing text and CSS
selectors.

### Identity and URL surface

Implement these fields with one consistent URL and content-reference policy:

| Member | Requirement |
| --- | --- |
| `key` | Stable lowercase identifier used in diagnostics and tests. |
| `home_url`, `featured_url`, `trending_url`, `creator_upload_url`, `creator_video_upload_url` | HTTPS entry points owned by the platform. |
| `default_content_kind` | The fallback kind used when a reference has no explicit kind. |
| `content_path_fragments` | Paths that the browser-side search extraction may treat as content links. |
| `content_url_templates` | Canonical HTTPS templates keyed by every supported content kind. |

The URL methods must have deterministic behavior:

- `parse_content_ref(value)` returns a normalized content ID and optional kind;
  reject blank, malformed, off-domain, and unsupported references.
- `search_url(keyword)` URL-encodes the query and rejects an empty keyword.
- `content_urls(content_ref)` returns only canonical URLs for supported kinds,
  in a documented order.
- `content_kind(value)`, `extract_content_id(value)`, and
  `extract_author_id(value)` return an explicit empty/`None` result when the
  value does not contain that information; they must not invent an ID.
- `is_platform_url(value)` accepts only the platform's supported HTTPS hosts
  and rejects lookalike domains.
- `is_publish_url(value, kind)` accepts only the platform's creator-upload and
  post-form routes for the requested media kind, so validation can distinguish
  a photo form, a video form, and an unrelated page.

The navigation methods—`navigate_home`, `navigate_featured`,
`navigate_search`, `navigate_trending`, `navigate_publish_image`, and
`navigate_publish_video`—should only select an entry point and let the shared
workflow own waiting, error handling, and result classification.

### Selector and marker surface

`PlatformSelectors` is intentionally explicit. Fill every field rather than
smuggling a platform-specific selector into shared code.

| Group | Members |
| --- | --- |
| Login and session | `login_text_keywords`, `login_panel_markers`, `logged_in_text_hints`, `login_qrcode_selectors`, `profile_ui_selectors`, `auth_cookie_names`, `phone_input_selectors`, `send_code_texts`, `verification_input_selectors`, `submit_code_texts`, `agreement_text` |
| Discovery and detail | `search_result_selectors`, `feed_card_selector`, `feed_content_id_attribute`, `trending_node_selectors`, `trending_topic_keywords`, `detail_desc_selectors`, `comment_item_selectors`, `like_button_selectors`, `favorite_button_selectors`, `comment_action_selectors`, `like_active_texts`, `favorite_active_texts`, `like_active_style_tokens`, `favorite_active_style_tokens`, `like_active_state_tokens`, `like_inactive_state_tokens`, `favorite_active_state_tokens`, `favorite_inactive_state_tokens`, `note_action_bar_marker`, `like_action_text`, `favorite_action_text`, `share_action_text`, `comment_action_text`, `copy_link_text` |
| Photo publishing | `publish_file_input_selector`, `publish_title_input_selector`, `publish_editor_selectors`, `publish_image_markers`, `music_open_selectors`, `music_open_texts`, `music_panel_selector`, `music_panel_markers`, `music_name_selectors`, `music_apply_selectors`, `music_apply_text`, `selected_music_text`, `publish_button_text`, `publish_success_texts`, `publish_success_path_fragment`, `topic_markers` |
| Video publishing | `publish_video_file_input_selector`, `publish_video_title_input_selector`, `publish_video_editor_selectors`, `publish_video_preview_selectors`, `publish_video_ready_texts`, `publish_video_progress_selectors`, `publish_video_failure_texts`, `publish_video_cover_control_selector`, `publish_video_empty_cover_text`, `publish_video_cover_dialog_markers`, `publish_video_cover_upload_markers`, `publish_video_cover_done_text`, `publish_video_cover_skip_horizontal_text` |

Prefer a small ordered fallback list of selectors that represent the same
semantic element. Scope selectors to visible, role-labelled, or otherwise
stable elements where possible. Do not use a broad selector that can match a
different destructive control. `auth_cookie_names` may identify cookie names
for a local login check; never log or store cookie values.

For toggle actions, put exact platform-owned active and inactive attribute
values in the corresponding `*_state_tokens` fields. The shared workflow only
clicks a toggle after a high-confidence inactive state and stops when evidence
is missing or contradictory; do not encode platform values in shared code or
treat the absence of an active color as proof of inactivity.

The remaining adapter fields are part of the page-state boundary:

- `risk_page_keywords` and `risk_strong_hints` surface verification or risk
  controls and must stop for the user instead of suggesting a bypass;
- `inaccessible_content_markers` distinguishes an inaccessible or unresolved
  detail page from a confirmed empty result.

Positive publish markers such as `publish_success_texts` and
`publish_success_path_fragment` are evidence to combine with the shared
workflow. A click is never confirmation by itself. Preserve the distinction
between `publish_confirmed` and `publish_clicked_unconfirmed`, and never
automatically retry the latter.

### Required methods

The adapter protocol also requires:

```python
def parse_content_ref(self, value: str) -> tuple[str, str | None]: ...
def search_url(self, keyword: str) -> str: ...
def content_urls(self, content_ref: str) -> list[tuple[str, str]]: ...
def content_kind(self, value: str) -> str | None: ...
def extract_content_id(self, value: str) -> str: ...
def extract_author_id(self, value: str) -> str: ...
def is_platform_url(self, value: str) -> bool: ...
def is_risk_page(self, title: str, text: str) -> bool: ...
def navigate_home(self, page) -> None: ...
def navigate_featured(self, page) -> None: ...
def navigate_search(self, page, keyword: str) -> None: ...
def navigate_trending(self, page) -> None: ...
def navigate_publish_image(self, page) -> None: ...
def navigate_publish_video(self, page) -> None: ...
```

Keep the adapter methods deterministic and side-effect-light. They may choose a
URL or classify visible text; they must not launch a second browser, bypass a
challenge, publish content, or change the shared result state.

## 4. Test the boundary before a live page

Add focused tests beside the existing
[`test_platform_adapter.py`](../tests/python/test_platform_adapter.py):

1. Assert the default adapter satisfies `PlatformAdapter` at runtime.
2. Test accepted IDs, every supported content kind, canonical URLs, malformed
   input, off-domain URLs, lookalike hosts, and unsupported schemes.
3. Inject the adapter into login, search, detail/interaction, and publishing
   workflows. Assert that navigation and generated JavaScript use the injected
   values rather than Douyin constants.
4. Parse generated browser expressions with Node.js. A Python test that only
   checks the string contents is not enough.
5. Test risk and inaccessible markers, including the stop/uncertain path. Do
   not turn an empty extraction or a click into a confirmed success.
6. Keep fixtures synthetic and privacy-safe. They should encode the minimum
   state needed for a decision, not captured HTML or a real session.

The repository's baseline checks remain required:

```bash
python -m compileall -q scripts tests/python
python -m unittest discover -s tests/python -v
python scripts/validate_fixtures.py
python scripts/validate_repository.py
npm run check
npm test
ruff check scripts tests/python
ruff format --check scripts tests/python
```

## 5. Manual validation and support claims

Automated tests prove the adapter contract and result semantics; they do not
prove that today's live page still exposes the same selectors. For an
authorized manual run, record:

- operating system, Chrome/Chromium version, date, and adapter version;
- account state and the exact command or workflow under test;
- visible login, risk, discovery, detail, and creator-page outcomes;
- sanitized selector or DOM clues for every changed page surface;
- scenarios not attempted, especially irreversible publishing actions.

Keep CAPTCHA, identity checks, and platform risk controls user-completed. If a
real publish is necessary, provide `--confirm` as a separate explicit step. If
the click cannot be confirmed, report the unresolved result, inspect the actual
page, and do not blind-retry. A passing manual run supports only the recorded
account, page version, and date; it is not proof of universal support.

Before advertising a new adapter, the pull request must explain its supported
scope, safety boundaries, test evidence, and remaining limits. The release
must still say which adapter is actually shipped. Use the shared result
contract in [`docs/RESULT_CONTRACT.md`](./RESULT_CONTRACT.md), the validation
boundaries in [`docs/VALIDATION.md`](./VALIDATION.md), and the contribution
rules in [`CONTRIBUTING.md`](../CONTRIBUTING.md) as the review baseline.

## Review checklist

- [ ] The adapter owns all platform URLs, content parsing, selectors, markers,
      and platform-specific policy text.
- [ ] Shared browser lifecycle, local profiles, loopback-only CDP, safety
      policy, and result semantics remain unchanged.
- [ ] Off-domain, malformed, and unsupported content references are rejected.
- [ ] Login, risk, inaccessible, and publish-uncertain states have tests.
- [ ] Generated browser expressions parse successfully.
- [ ] No account data, session data, private content, or real browser profile is
      committed.
- [ ] The PR does not claim another platform is supported without repeatable
      evidence and an authorized manual validation path.
