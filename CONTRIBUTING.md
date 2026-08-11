# Contributing

Thank you for helping improve `douyin-skills`. The most useful contributions solve a real user problem, preserve the project's safety model, and make the evidence as clear as the implementation.

## Good ways to help

- report a reproducible Douyin page change with sanitized evidence;
- turn a selector regression into a focused fixture or test;
- make result states more precise without overstating success;
- document a verified installation on another Agent Skills client;
- help separate reusable browser runtime code from platform-specific behavior;
- improve the English or Chinese documentation without letting the two guides contradict each other.

Use [GitHub Discussions](https://github.com/zJay26/douyin-skills/discussions) for open-ended workflow, Agent client, or future-adapter ideas. Open an Issue when the work is specific enough to reproduce and verify.

## Local development

You need Python 3.9+, Node.js 18+, npm, and Chrome/Chromium.

```bash
npm install
python scripts/cli.py doctor
python -m unittest discover -s tests/python -v
npm run check
npm test
```

Code style uses Ruff 0.16.2:

```bash
python -m pip install ruff==0.16.2
ruff check scripts tests/python
ruff format --check scripts tests/python
```

## Change guidelines

1. Keep each commit focused on one class of change. Use a clear imperative message such as `fix: reject unsafe publish retry`.
2. Add tests for behavior changes and update the relevant `SKILL.md` and README contract.
3. For selector changes, state the page, Chrome version, account state, and scenarios you did **not** verify.
4. Do not commit `node_modules/`, `__pycache__/`, cookies, phone numbers, verification codes, QR codes, account configuration, or Chrome profiles.
5. Do not add captcha bypasses, engagement inflation, account farming, or unauthorized account actions.
6. Do not advertise another Agent client or social platform as supported without a repeatable validation path.

## Pull requests

Explain the user problem, the solution, validation evidence, and remaining limits. Sanitize real-page screenshots and logs. Documentation-only changes should still run relative-link and GitHub Markdown rendering checks.

Report security vulnerabilities privately through [SECURITY.md](SECURITY.md).
