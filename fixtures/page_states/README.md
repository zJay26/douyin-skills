# Sanitized page-state fixtures

These versioned fixtures protect the runtime's certainty semantics against page-drift regressions without committing a real browser session. Every file under `v1/` is hand-authored synthetic JSON. It is not captured HTML and is not evidence that a current Douyin account or page passed an end-to-end test.

## Schema v1

Each fixture contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Fixture schema version, currently `1.0`. |
| `id` | Stable lowercase kebab-case identifier. |
| `flow` | One of `login`, `search`, `detail`, or `publish`. |
| `description` | The regression boundary being protected. |
| `source` | Must be exactly `{"kind":"synthetic","contains_real_account_data":false}`. |
| `input` | Minimal state consumed by the production classifier. |
| `expected` | Fields that must appear in the classified result. |

Run the validation directly:

```bash
python scripts/validate_fixtures.py
```

The validator checks the schema, IDs, required flow coverage, expected classifier results, canonical HTTPS Douyin URLs, and privacy rules. For a focused page-drift regression, filter by workflow or stable fixture ID:

```bash
python scripts/validate_fixtures.py --flow detail
python scripts/validate_fixtures.py --fixture-id detail-page-drift
```

Filtered runs keep the schema, expected-result, URL, and privacy checks but intentionally do not require every workflow to be present. An unknown filter exits with status `2`.

## Privacy rules

Do not copy a browser dump into this directory. Fixtures must never contain:

- cookies, session IDs, authorization tokens, QR codes, or embedded images;
- phone numbers, email addresses, account IDs, or user-specific profile paths;
- real captions, comments, drafts, analytics, or unpublished content;
- local Windows, macOS, Linux, or WSL paths;
- URLs outside the public `www.douyin.com` and `creator.douyin.com` hosts.

Use clearly synthetic IDs, handles, titles, and descriptions. A page-drift report can describe the observable state and then reproduce it with the smallest synthetic fixture; the original sensitive page content must remain local.

## Adding a regression

1. Choose the existing flow whose result contract changed or failed.
2. Add the smallest synthetic `v1/*.json` state that reproduces the decision.
3. Record only expected fields that matter to the certainty boundary.
4. Run the fixture validator, Python tests, and repository validator.
5. State separately whether the report came from a dated manual run or a synthetic hypothesis.

Create a new schema directory only when the fixture structure itself is incompatible. Adding optional input fields or another fixture does not require a new schema version.
