# Runtime diagnostics and migration

## Discover the installed CLI

```bash
python scripts/cli.py version
python scripts/cli.py capabilities
```

Both commands work without Chrome, Node dependencies, or an account. `capabilities` describes all 30 commands, their actual flags, required arguments, defaults, numeric limits, effect category, and confirmation requirement. Global options belong before the command. Unknown optional fields must be tolerated.

`effect` is descriptive metadata, not authorization. `browser_read` commands can navigate or reveal login UI; `browser_form` commands can upload media. Only `browser-status` is strictly attach-only and does not change pages. A command's `requires_confirmation` field describes its CLI flag, not whether the user has authorized the action.

Invalid arguments produce one JSON object, exit code `2`, and `error_code: invalid_arguments`. `--help` remains human-readable text. Long-option abbreviations are disabled, so publishing requires the complete `--confirm` spelling.

## Inspect or select a browser page

```bash
python scripts/cli.py --port 9222 browser-status
python scripts/cli.py --port 9222 browser-status --include-tabs
python scripts/cli.py --port 9222 --target-id <target-id> validate-publish-video
```

`browser-status` reads the browser/protocol version, page count, and whether the saved target still exists. A connection failure is reported without launching Chrome. It does not inspect DOM content or prove login. Titles and URLs appear only with `--include-tabs`; keep that output local. Debugger WebSocket addresses are never included in this command's result.

`--target-id` selects an existing page and saves it for later commands on the same endpoint and profile. A missing target or a worker target is an error. This option never launches or restarts Chrome; if the page needs human verification, handle it in that browser. Other loopback endpoints, including `::1`, are attach-only; automatic Chrome launch binds to `127.0.0.1`.

Without an explicit target, the CLI reuses its saved page. If it is missing or closed, login/discovery/form preparation creates a dedicated tab. Follow-up publishing commands require a saved form and stop rather than choosing another tab. Commands operating on the same profile and page should run sequentially.

### Upgrading from v1.4 and earlier

Session pointers now live under `DOUYIN_SKILLS_HOME/runtime` (default `~/.douyin-skills/runtime`) and are separated by endpoint and profile. Old temporary-directory pointers are not adopted automatically. Account configuration and Chrome profiles are preserved. To resume an existing publish form after upgrading, inspect local tabs and choose its target explicitly as shown above.

## Account maintenance

```bash
python scripts/cli.py update-account --name work --description "Creator account"
```

Account mutations use an OS process lock and atomic replacement. Concurrent account updates cannot overwrite another writer's changes. Locks are released when a process exits; a busy lock produces a bounded error. Names must be valid across Windows, macOS, and Linux. Duplicate ports, case-insensitive duplicate names, corrupt JSON, and unsafe paths are rejected without rewriting the configuration. Removing an account registration preserves its profile data.

`doctor` verifies Node.js is at least version 18 and retains dependency diagnostics when account configuration is invalid. `accounts.count: null` means the configuration could not be read, not that no accounts exist.

## Transport errors and uncertain actions

The shared Python client is `scripts/browser_runtime.py`; `douyin.cdp` retains compatibility imports. Requests use UTF-8 stdin, avoiding Windows argument-length limits. The bridge validates both HTTP and advertised WebSocket loopback endpoints, rejects malformed responses, and bounds HTTP, CDP-command, and total-operation timeouts. Browser communication never retries a command automatically.

The bridge interprets [`Runtime.evaluate.exceptionDetails`](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-evaluate) and [`Page.navigate.errorText`](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-navigate) as failures. Transport failures expose `error_code`, including `evaluation_failed`, `navigation_failed`, `invalid_endpoint`, `invalid_response`, `target_not_found`, `timeout`, and operating-system connection codes.

An error during a publish/comment/toggle dispatch cannot prove that nothing happened. These paths preserve `clicked: null` and `retry_safe: false`; a known click followed by a failed read remains unconfirmed. See the [result contract](./RESULT_CONTRACT.md) before deciding what to report or retry.
