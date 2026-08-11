

<div align="center">
  <h1>douyin-skills</h1>
  <p><strong>Out-of-the-box Douyin Automation Skills</strong></p>
  <p><strong>Supports login, search, image-text publishing, liking, favoriting, and sharing. Can be integrated as an OpenClaw Skill.</strong></p>

  <p>
    <a href="./LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License: MIT">
    </a>
    <a href="https://www.python.org/">
      <img src="https://img.shields.io/badge/Python-3.x-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    </a>
    <a href="https://nodejs.org/">
      <img src="https://img.shields.io/badge/Node.js-required-43853d?style=for-the-badge&logo=node.js&logoColor=white" alt="Node.js">
    </a>
    <a href="https://docs.openclaw.ai">
      <img src="https://img.shields.io/badge/OpenClaw-Compatible-6f42c1?style=for-the-badge" alt="OpenClaw Skill">
    </a>
  </p>
</div>

---

## 📖 Project Introduction

`douyin-skills` is a collection of automation tools designed for the **Douyin Web Version / Creator Center Web Version**, covering common workflows such as login, search, image-text publishing, and basic interactions.

### Sub-Skill Descriptions

|Sub-Skill|Purpose|
|-|-|
|`douyin-auth`|Login status check, QR code login, SMS verification login, multi-account management|
|`douyin-explore`|Search works by keyword, get details by work ID|
|`douyin-publish`|Fill out image-text publish form, select music, execute publish|
|`douyin-interact`|Like, favorite, and share links on public works|
|`douyin-env`|Describes dependency environments, migration requirements, and deployment self-check process|

\---

## 📦 Installation

1. Click **Code → Download ZIP** on the GitHub repository page
2. Place the extracted `douyin-skills` folder into the corresponding path:

##### OpenClaw

```bash
<openclaw-project>/skills/douyin-skills/
```

\---

## 🚀 Quick Start

**First, let the Agent complete the environment configuration based on the `douyin-env` skill, then directly use natural language to instruct the Agent to operate Douyin. You will need to log in to the Douyin Web Version manually the first time. After that, login information will be remembered automatically. Occasionally, you may encounter a security verification page; in this case, you need to launch the browser in headed mode and manually complete the verification.**

\---

## 🔮 Future Extensions

The following capabilities are currently not supported:

* Comments
* Reply to comments
* Video publishing
* Scheduled publishing
* Data analytics dashboard
* Complex batch operations
* Full Creator Center workflow automation

\---

## 🗂️ Repository Structure

```text
.
├── LICENSE
├── README.md
├── SKILL.md
├── scripts/
│   ├── account\_manager.py
│   ├── cdp\_client.mjs
│   ├── chrome\_launcher.py
│   ├── cli.py
│   └── douyin/
│       ├── \_\_init\_\_.py
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

### Directory Description

* `SKILL.md`: Main Skill entry point
* `skills/\*/SKILL.md`: Sub-Skills split by functionality
* `scripts/cli.py`: Unified command entry
* `scripts/douyin/\*`: Underlying Douyin page automation logic
* `scripts/chrome\_launcher.py`: Browser launch and mode switching
* `scripts/cdp\_client.mjs`: Node-side CDP communication bridge

\---

## 📜 Current Commands

### 🔐 Authentication / Accounts

|Command|Description|
|-|-|
|`check-login`|Check current login status|
|`get-qrcode`|Get QR code for QR login|
|`wait-login`|Wait for user to complete QR login|
|`send-code`|Send SMS verification code|
|`verify-code`|Verify SMS code|
|`list-accounts`|List saved accounts|
|`add-account`|Add new account|
|`remove-account`|Remove account|
|`set-default-account`|Set default account|

### 🔍 Search / Content Discovery

|Command|Description|
|-|-|
|`search-videos`|Search works by keyword|
|`get-video-detail`|Get details by work ID|

### 📝 Image-Text Publishing

|Command|Description|
|-|-|
|`fill-publish-image`|Fill out image-text publish form and upload images|
|`select-music`|Select background music|
|`click-publish`|Execute publish action|

### ❤️ Basic Interactions

|Command|Description|
|-|-|
|`like-video`|Like a work|
|`favorite-video`|Favorite a work|
|`share-video`|Share work link|

\---

## 💻 Operating Mechanism

* Runs in **headless** mode by default.
* Switches to **headed** mode only when a **captcha / identity verification / risk control page** is detected, requiring the user to manually complete the verification.
* Image-text publishing defaults to: **vertical images + manual review before publishing** to avoid top/bottom whitespace, white bars, abnormal elements, or cover cropping issues.

\---

## ⚙️ Environment Requirements (The Agent can automatically configure the environment based on the `douyin-env` skill)

### Required Binaries

* `python3`
* `node`
* `npm`
* Chrome / Chromium

### Required Dependencies

* Node package: `ws`
* Python package: `Pillow`

### Browser Requirements

The browser needs to support remote debugging. The script will try one of the following names:

* `google-chrome`
* `google-chrome-stable`
* `chromium`
* `chromium-browser`
* `chrome`

It can also be specified via environment variable:

```bash
CHROME_BIN=/path/to/chrome
```

\---

## 📄 License

This project uses the MIT License. Free use and secondary development are welcome.
