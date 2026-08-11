# Security policy

## Supported version

Security fixes target the latest commit on `main`. Older commits do not receive separate security patches.

## Report a vulnerability privately

Use GitHub's [private vulnerability reporting](https://github.com/zJay26/douyin-skills/security/advisories/new). Do not open a public Issue containing exploit details.

Include the affected version, reproduction conditions, potential impact, and a suggested fix when possible. Never attach real cookies, phone numbers, verification codes, QR codes, account configuration, or Chrome profiles. Use fully sanitized examples.

## Project security boundaries

- Chrome DevTools Protocol binds only to `127.0.0.1`.
- Login and account data remain on the user's machine and must not be committed or sent to third parties.
- Captcha, identity, and risk checks require manual completion in a visible browser.
- Publishing requires explicit confirmation; an unconfirmed result must not be retried automatically.
- The project does not accept platform-control bypasses, engagement inflation, account farming, or unauthorized account actions.
- Future Agent client or platform adapters must preserve these boundaries rather than weakening them for compatibility.

Use a public Issue for ordinary defects after removing all sensitive data.
