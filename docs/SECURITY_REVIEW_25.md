# Issue #25: security review and regression scope

Reviewed on 2026-11-05 against main commit
`09e9ccb6c484c59d69e11dbb4bc975c47e5510e5` (v1.6.0). Sources:
[original evaluation](https://github.com/zJay26/douyin-skills/issues/25),
[initial live-page report](https://github.com/zJay26/douyin-skills/issues/25#issuecomment-6391337078),
and [reviewer's recovery confirmation](https://github.com/zJay26/douyin-skills/issues/25#issuecomment-6397033651).
The following distinguishes repository evidence from the reviewer's local results.

| # | Suggestion | Current main evidence | Change / remaining status |
| --- | --- | --- | --- |
| 1 | Multi-signal captcha/risk detection | Text keywords dominate; login's explicit risk UI was gated by `hasRiskKeyword`; other flows drop structural signals. | Addressed: shared visible frame/control/image and URL signals, English challenge text, inspection failure stop, propagation through login/search/interaction/publishing. Synthetic tests cover stopping before actions. Future live platform variants still require validation. |
| 2 | Keep phone/code out of argv | `send-code --phone` and `verify-code --code` pass values in argv. | Secure stdin and named-environment sources added; mutually exclusive, missing sources rejected, no-echo terminal input, no background worker on auth commands. Old flags remain deprecated for compatibility and **retain their argv/history risk** until callers migrate. This is a migration path, not retroactive protection of legacy invocations. |
| 3 | Private, unique QR files; no raw QR JSON | Fixed shared temporary path, no explicit permission guarantee, full data URL in output. | Addressed: exclusive random directory and filename, POSIX `0700`/`0600`, path-only JSON, cleanup on write failures, invalid data rejected before file creation. Windows ACL semantics require host-specific verification. |
| 4 | Reduce repeated CLI handlers | Repeated connect/action/risk/output handlers remain. | Still present; cosmetic refactor deferred to keep this security change small. |
| 5 | Prevent command/effect/dispatch drift | Parser, `COMMAND_EFFECTS`, and local dispatch are separate. Existing CLI tests exercise command enumeration/capabilities but do not derive all three from one registry. | Still present; no registry rewrite in this patch. |
| 6 | Remove Douyin selector from search readiness wait | `search_videos` still checks `.search-result-card` outside adapter selectors. | Still present; independent adapter-boundary change deferred. No unrelated live selector replacements. |
| 7 | Avoid private argparse APIs | `cli_contract._arguments` and `capabilities_payload` use `_actions` / `_SubParsersAction`. | Dependency still present. A current failure is not established; the existing CI matrix tests Python 3.9 and 3.13. Future-version compatibility requires verification. |
| 8 | Dedicated search/feeds tests | Existing `test_page_states.py` and `test_platform_adapter.py` already cover search, trending and detail; no `test_search.py` and no successful `list_feeds` regression. | Partially covered, not zero coverage. This patch adds risk-stop regressions for all four read flows and late structural signals. Full extraction/happy-path feeds and live drift coverage remain to be added. |
| 9 | Execute waiter polling in tests | Search tests mock `wait_for_meaningful_text`; no direct min-length/timeout tests. | Addressed by `test_waiters.py`: real loop execution with a controlled clock, trimmed min length, timeout/zero timeout, immediate textless-risk return. |
| 10 | Synchronize Chinese video-publishing FAQ | Chinese FAQ incorrectly excludes video publishing while English FAQ/code support guarded publishing. | Addressed by the one-line Chinese FAQ correction. |

## Recovered live-page reports

The evaluator explicitly confirmed that `get-video-detail`,
`get-trending-topics`, and `get-interaction-state` had recovered on 2026-10-25.
Record these as **recovered**, not persistent defects or fixes delivered by this
patch. The evaluator also mentioned a local adapter fallback edit; that does not
prove an upstream change. Existing synthetic detail/trending/page-drift tests are
useful regression evidence, but cannot certify today's live selectors. No current
authenticated Douyin session was exercised during this review.

The evaluator's local Chrome-profile chmod is likewise not an upstream fix.
Profile-directory POSIX modes or Windows ACLs need inspection on the deployment
host; do not infer them from the report.

## Focused regression checks

```bash
python -m unittest discover -s tests/python -p 'test_auth_security.py' -v
python -m unittest discover -s tests/python -p 'test_risk_detection.py' -v
python -m unittest discover -s tests/python -p 'test_waiters.py' -v
```

These cover stdin/env/legacy behavior and output redaction; unique concurrent QR
files, POSIX modes, pre-existing symlink avoidance, invalid input and failed-write
cleanup; textless DOM and English evidence; authenticated UI not overriding a
captcha; and login/read/interaction/publish stops before control dispatch.
The DOM expression is executed in Node with controlled elements, and the existing
real-Chrome smoke additionally checks local synthetic DOMs. All data is synthetic;
no verification is solved or bypassed, and no real content is posted.

Run the standard repository CI for the full suite, fixtures, lint, Node bridge,
real local-browser smoke and deterministic release checks. See
[validation boundaries](./VALIDATION.md) and the
[authentication contract](./RESULT_CONTRACT.md#sensitive-authentication-input).
