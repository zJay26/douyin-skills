<div align="center">

# douyin-skills

**A focused OpenClaw skill collection for practical Douyin web automation**

Authentication, search, image-post publishing, and lightweight interactions — trimmed down to the workflows that are actually worth keeping.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-required-43853d?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-6f42c1?style=for-the-badge)](https://docs.openclaw.ai)

</div>

---

## Why this repo exists

Most Douyin automation projects try to do too much too early:
- comments
- analytics
- batch workflows
- unstable page scraping promises
- broad claims that break the moment the site changes

This repository takes the opposite approach.

It keeps a **small, explicit, working surface area**:
- login and account switching
- keyword search
- detail lookup
- image-post publishing
- like / favorite / share-link
- environment setup guidance for moving the skill to another machine

In short:

> **This is not “full Douyin automation.”**  
> It is a cleaned, practical OpenClaw skill set for a few repeatable web workflows that have actually been exercised and trimmed for stability.

---

## Features

### Authentication & account management
- Check login status
- QR login flow
- SMS verification flow
- Named account profiles
- Default account switching

### Explore
- Search Douyin items by keyword
- Fetch detail by item id

### Publish
- Fill image-post form
- Select background music
- Publish after page confirmation

### Interact
- Like a note/video
- Favorite a note/video
- Open share panel and copy link

### Environment setup
- Explain the runtime requirements
- Explain what must be copied to another machine
- Explain how to self-check a deployment

---

## What this project intentionally does **not** promise

The following are **out of scope** for the current public surface:
- comments
- reply comments
- video publishing
- scheduled publishing
- analytics dashboards
- creator-center full workflow automation
- batch interaction pipelines
- “stable API-like” guarantees

This repository was deliberately cleaned to avoid exposing commands that looked complete but were not worth promising.

---

## Repository structure

```text
.
├── LICENSE
├── README.md
├── SKILL.md
├── scripts/
│   ├── account_manager.py
│   ├── cdp_client.mjs
│   ├── chrome_launcher.py
│   ├── cli.py
│   └── douyin/
│       ├── __init__.py
│       ├── cdp.py
│       ├── errors.py
│       ├── interact.py
│       ├── login.py
│       ├── publish.py
│       ├── search.py
│       ├── selectors.py
│       ├── urls.py
│       └── waiters.py
└── skills/
    ├── douyin-auth/
    ├── douyin-env/
    ├── douyin-explore/
    ├── douyin-interact/
    └── douyin-publish/
```

### Directory roles
- `SKILL.md` — main OpenClaw skill entry
- `skills/*/SKILL.md` — subskills split by concern
- `scripts/cli.py` — main command entrypoint
- `scripts/douyin/*` — low-level browser automation logic
- `scripts/chrome_launcher.py` — Chrome / Chromium launch and mode switching
- `scripts/cdp_client.mjs` — CDP bridge used by the Python layer

---

## Current command surface

### Authentication / account
- `check-login`
- `get-qrcode`
- `wait-login`
- `send-code`
- `verify-code`
- `list-accounts`
- `add-account`
- `remove-account`
- `set-default-account`

### Explore
- `search-videos`
- `get-video-detail`

### Publish
- `fill-publish-image`
- `select-music`
- `click-publish`

### Interact
- `like-video`
- `favorite-video`
- `share-video`

This is the intentionally reduced, “core-only” command set.

---

## Runtime model

By default the skill prefers **headless mode**.

If a real verification / risk page is detected, the launcher can switch to **headed mode** so a human can complete the challenge.

Why this matters:
- Douyin behaves differently in headless vs headed sessions
- creator-center flows and public-page flows are not identical
- newly published items are often easier to re-find from the user homepage than from search

This repo therefore prefers:
1. minimal command surface
2. explicit fallback behavior
3. fewer false promises

---

## Requirements

### Required binaries
- `python3`
- `node`
- `npm`
- Chrome / Chromium

### Required dependencies
- Node package: `ws`
- Python package: `Pillow` *(only needed if you also use local image-generation helpers)*

### Browser requirement
The browser must support remote debugging.
The launcher will try one of:
- `google-chrome`
- `google-chrome-stable`
- `chromium`
- `chromium-browser`
- `chrome`

You can also set:

```bash
CHROME_BIN=/path/to/chrome
```

---

## Install

### 1. Clone

```bash
git clone <your-repo-url>
cd douyin-skills
```

### 2. Install Node dependency

```bash
npm install ws
```

### 3. Install Python dependency

```bash
pip install pillow
```

---

## Quick start

### Check login status

```bash
python3 scripts/cli.py check-login
```

### Get login QR code

```bash
python3 scripts/cli.py get-qrcode
```

### Wait for login completion

```bash
python3 scripts/cli.py wait-login
```

### Search

```bash
python3 scripts/cli.py search-videos --keyword "AI焦虑" --limit 7
```

### Fetch detail

```bash
python3 scripts/cli.py get-video-detail --video-id 7619615485310668078
```

### Fill an image-post draft

```bash
python3 scripts/cli.py fill-publish-image \
  --title "你的标题" \
  --desc-file /abs/path/desc.txt \
  --images /abs/path/pic1.jpg /abs/path/pic2.jpg
```

### Pick music

```bash
python3 scripts/cli.py select-music
```

### Publish

```bash
python3 scripts/cli.py click-publish
```

### Interact with a published item

```bash
python3 scripts/cli.py like-video --video-id 7619615485310668078
python3 scripts/cli.py favorite-video --video-id 7619615485310668078
python3 scripts/cli.py share-video --video-id 7619615485310668078
```

---

## Notes on publishing

Publishing is intentionally simple:
1. fill the form
2. select music
3. visually / programmatically inspect page state
4. publish

A previous public `validate-publish` command was removed from the public surface because it was useful as a helper but not reliable enough to deserve first-class status.

---

## Notes on newly published items

Do **not** assume search will find a newly published item immediately.

A more reliable path is:
1. open your own Douyin homepage
2. find the new item in the post list
3. extract the real public `note` / `video` link
4. then interact with that real public item

This matters especially for like / favorite right after publishing.

---

## OpenClaw skill layout

This repository is meant to be used as an OpenClaw skill folder.

### Main skill
- `SKILL.md`

### Subskills
- `skills/douyin-auth/`
- `skills/douyin-env/`
- `skills/douyin-explore/`
- `skills/douyin-interact/`
- `skills/douyin-publish/`

The split is intentional:
- auth is different from publish
- publish is different from explore
- environment setup is different from daily operation

---

## Limitations

This project automates a live consumer website and creator-center UI.
That means it can break when Douyin changes:
- DOM structure
- anti-bot behavior
- login flow
- creator-center upload behavior
- note/video interaction layout

Treat this repository as a maintained automation utility, **not** a stable external API.

---

## Roadmap ideas

Potential future work, if worth keeping stable enough:
- stricter environment self-check tooling
- more explicit machine-setup scripts
- better publish-state introspection
- more robust creator-center recovery logic

Not all ideas should become public commands.
The bar should stay high.

---

## Contributing

If you extend this repo, prefer the same philosophy:
- keep the surface small
- remove unstable promises
- favor explicit workflows over marketing claims
- do not expose half-working commands as public features

If a feature is not stable enough to be defended, keep it private or cut it.

---

## License

This project is licensed under the MIT License.  
See [LICENSE](./LICENSE).
