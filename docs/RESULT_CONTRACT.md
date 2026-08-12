# JSON result contract

`douyin-skills` uses JSON as the boundary between an Agent client and the local browser runtime. Clients can discover the installed versions without starting Chrome:

```bash
python scripts/cli.py version
```

```json
{
  "success": true,
  "project": "douyin-skills",
  "version": "1.0.1",
  "result_contract_version": "1.0"
}
```

The project version follows semantic versioning. The result-contract version describes the cross-command JSON vocabulary independently, so an integration can decide whether it understands the installed runtime.

## Stable minimum envelope

Every command writes one JSON object to standard output. The minimum common field is:

| Field | Type | Meaning |
| --- | --- | --- |
| `success` | boolean | The command reached its own defined outcome. It is not, by itself, proof that a remote state change was confirmed. |

On failure, commands provide a human-readable `error` or `message` when one is available. Top-level CLI exceptions also include `error_type`. Commands add fields appropriate to their domain, such as `items`, `logged_in`, `status`, `validation`, or `url`.

Consumers must tolerate unknown fields. New optional fields may be added within result-contract 1.x; removing a required field or changing an existing field's meaning requires a new major contract version.

## Outcome certainty

`success: true` means that the command completed according to its command-level contract. For actions that can change remote state, inspect the certainty fields as well:

| Result | What is known | Safe Agent behavior |
| --- | --- | --- |
| `status: publish_confirmed` | The page exposed an explicit post-publish success signal. | Report that publication was confirmed. |
| `status: publish_clicked_unconfirmed` | One publish click occurred, but the resulting page did not provide reliable confirmation. | Report uncertainty, ask the user to check Creator Center, and do **not** retry. |
| `state_verified: false` | An interaction click may have occurred, but the final like/favorite state was not reliably observed. | Describe the click only; do not claim the final state or click again. |
| `needs_user_verification: true` | A captcha, identity check, or risk-control state needs a person. | Surface the visible browser and stop until the user completes the step. |
| `success: false` | The requested command did not reach its defined successful outcome. | Read `error`, `message`, and any validation details before deciding what to do. |

The absence of a certainty field must never be upgraded into a stronger claim. In particular, a successful button dispatch is not automatically a confirmed platform outcome.

## Process exit codes

| Code | Meaning |
| --- | --- |
| `0` | The command reached its defined successful result. Inspect certainty fields before describing any remote state. |
| `1` | A normal negative state was observed, currently used for login checks that remain logged out. |
| `2` | Invalid input, a failed prerequisite, user verification, a blocked operation, or another command error. |

JSON is authoritative for program behavior; exit codes are a coarse shell-level signal.

## Integration rules

1. Call `version` before depending on fields introduced by a particular contract version.
2. Parse standard output as JSON and keep standard error for diagnostics.
3. Require an explicit user decision before calling `click-publish --confirm`.
4. Never retry an irreversible action when its prior result is unconfirmed.
5. Preserve `needs_user_verification` as a supported pause state rather than treating it as a bypass target.
6. Avoid logging or transmitting account configuration, cookies, QR codes, phone numbers, or Chrome profile data.
