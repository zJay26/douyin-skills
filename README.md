# douyin-skills

A focused OpenClaw skill collection for Douyin web automation.

It currently keeps a deliberately small, practical surface area:
- authentication / account switching
- video search and detail lookup
- image-post publishing
- lightweight interactions: like, favorite, share-link
- environment setup guidance for moving the skill to another machine

The goal of this repository is **not** to promise full Douyin automation.
It is a trimmed, working skill set for a few repeatable workflows that have actually been exercised.

---

## What this repo contains

```text
.
├── SKILL.md
├── scripts/
│   ├── cli.py
│   ├── chrome_launcher.py
│   ├── cdp_client.mjs
│   ├── account_manager.py
│   └── douyin/
│       ├── login.py
│       ├── search.py
│       ├── publish.py
│       ├── interact.py
│       ├── cdp.py
│       ├── selectors.py
│       ├── urls.py
│       └── ...
└── skills/
    ├── douyin-auth/
    ├── douyin-env/
    ├── douyin-explore/
    ├── douyin-interact/
    └── douyin-publish/
```

This repo is the **skill itself**.
It does not try to bundle every local asset from the original workspace.

---

## Current capabilities

### 1. Authentication
- check login status
- QR login flow
- SMS verification flow
- named account profiles
- default account switching

### 2. Explore
- search videos by keyword
- fetch item detail by id

### 3. Publish
- fill image-post form
- select music
- click publish

### 4. Interact
- like a note/video
- favorite a note/video
- open share panel and copy link

### 5. Environment setup
- documents what is required to move the skill to another machine
- documents the minimal dependency stack

---

## Intentionally out of scope

These are **not** promised by this repo:
- comments
- reply comments
- video publishing
- scheduled publishing
- analytics dashboards
- full creator-center automation
- complex batch operations

The repository was explicitly cleaned up to remove unstable or misleading surfaces.

---

## Requirements

### Required binaries
- `python3`
- `node`
- `npm`
- Chrome / Chromium

### Required runtime dependencies
- Node package: `ws`
- Python package: `Pillow` (only needed for local image-generation helpers if you use them)

### Browser requirement
The browser must support remote debugging.
The launcher will try one of:
- `google-chrome`
- `google-chrome-stable`
- `chromium`
- `chromium-browser`
- `chrome`

You can also point it explicitly with:
- `CHROME_BIN=/path/to/chrome`

---

## Install

### 1. Clone the repository

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

### Check login

```bash
python3 scripts/cli.py check-login
```

### Get QR code

```bash
python3 scripts/cli.py get-qrcode
```

### Wait for login

```bash
python3 scripts/cli.py wait-login
```

### Search videos

```bash
python3 scripts/cli.py search-videos --keyword "AI焦虑" --limit 7
```

### Get detail

```bash
python3 scripts/cli.py get-video-detail --video-id 7619615485310668078
```

### Fill image post

```bash
python3 scripts/cli.py fill-publish-image \
  --title "你的标题" \
  --desc-file /abs/path/desc.txt \
  --images /abs/path/pic1.jpg /abs/path/pic2.jpg
```

### Select music

```bash
python3 scripts/cli.py select-music
```

### Publish

```bash
python3 scripts/cli.py click-publish
```

### Like / favorite / share

```bash
python3 scripts/cli.py like-video --video-id 7619615485310668078
python3 scripts/cli.py favorite-video --video-id 7619615485310668078
python3 scripts/cli.py share-video --video-id 7619615485310668078
```

---

## Runtime model

By default the skill now prefers **headless mode**.

If a real verification page is detected, it switches to **headed mode** and asks the user to finish verification manually.

This is important because Douyin web flows are not equally stable across:
- headless vs headed
- feed vs search vs creator-center pages
- note vs video item pages

---

## Notes on publishing

Publishing is intentionally kept simple:
- fill the form
- select music
- inspect page state
- publish

The repository no longer exposes a separate `validate-publish` command because page-state checks were useful but not reliable enough to deserve a first-class public command.

---

## Notes on newly published posts

For operations right after publishing, do **not** assume search will find the item immediately.
A more reliable path is:
1. open your own Douyin homepage
2. find the newly published note in the post list
3. extract the real public `note` / `video` link
4. then interact with it

---

## OpenClaw integration

This repository is structured as an OpenClaw skill folder.
The main entry is:
- `SKILL.md`

Subskills are split by concern:
- `skills/douyin-auth/`
- `skills/douyin-env/`
- `skills/douyin-explore/`
- `skills/douyin-interact/`
- `skills/douyin-publish/`

---

## Limitations

This project depends on a live consumer website and creator-center UI.
That means selectors, flows, and browser behavior may break when Douyin changes:
- DOM structure
- anti-bot checks
- login flow
- creator-center upload behavior

Treat it as a maintained automation utility, not a guaranteed stable API.

---

## License

MIT. See [LICENSE](./LICENSE).
