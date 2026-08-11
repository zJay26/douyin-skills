## What changed

Describe the user problem, the solution, and the boundary you deliberately did not expand.

## Validation

- [ ] `python -m unittest discover -s tests/python -v`
- [ ] `npm test`
- [ ] `npm run check`
- [ ] `ruff check scripts tests/python`
- [ ] `ruff format --check scripts tests/python`

For real-page changes, include the browser version, account state, page result, and a sanitized screenshot or DOM clue. Never upload cookies, verification codes, QR codes, phone numbers, or Chrome profiles.

## Safety and compatibility

- [ ] Loopback-only CDP, human verification, publish confirmation, and reasonable-frequency boundaries remain intact
- [ ] No secrets, session data, personal identifiers, or local profiles are included
- [ ] Skill and README documentation match the actual CLI behavior
- [ ] Any new Agent client or platform claim has a repeatable validation path
