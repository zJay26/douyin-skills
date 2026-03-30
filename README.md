<div align="center">

# douyin-skills

**开箱即用的抖音网页自动化Skills**  
**支持登录、搜索、图文发布、点赞、收藏、分享，可作为 OpenClaw Skill 集成使用。**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-required-43853d?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Compatible-6f42c1?style=for-the-badge)](https://docs.openclaw.ai)

</div>

---

## 📖 项目简介

`douyin-skills` 是一个面向 **抖音网页版 / 创作者中心网页版** 的自动化工具集，覆盖登录、搜索、图文发布与基础互动等常见工作流。

### 子 Skill 说明

| 子 Skill | 作用 |
|---|---|
| `douyin-auth` | 登录状态检查、二维码登录、短信验证码登录、多账号管理 |
| `douyin-explore` | 按关键词搜索作品、根据作品 ID 获取详情 |
| `douyin-publish` | 填写图文发布表单、选择音乐、执行发布 |
| `douyin-interact` | 对公开作品执行点赞、收藏、分享链接 |
| `douyin-env` | 说明依赖环境、迁移要求与部署自检流程 |

---

## 📦 安装方式

1. 在 GitHub 仓库页面点击 **Code → Download ZIP**  
2. 将解压后的 `douyin-skills` 文件夹放入对应路径：

##### OpenClaw
```bash
<openclaw-project>/skills/douyin-skills/
```

---

## 🚀 快速开始

**先让Agent根据douyin-env skill完成环境配置，之后直接用自然语言指挥Agent操作抖音就行了。第一次需要手动登录抖音网页版，之后会自动记住登录信息，偶尔可能会遇到风控页，此时需要以有头模式启动浏览器并手动过验证。**

---

## 🔮 未来拓展

暂不支持以下能力：

- 评论
- 回复评论
- 视频发布
- 定时发布
- 数据分析面板
- 复杂批量运营
- 完整创作者中心工作流自动化

---

## 🗂️ 仓库结构

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

### 目录说明

- `SKILL.md`：主 Skill 入口
- `skills/*/SKILL.md`：按功能拆开的子 Skill
- `scripts/cli.py`：统一命令入口
- `scripts/douyin/*`：底层抖音页面自动化逻辑
- `scripts/chrome_launcher.py`：浏览器启动与模式切换
- `scripts/cdp_client.mjs`：Node 侧 CDP 通信桥接

---

## 📜 当前命令

### 🔐 认证 / 账号
| 命令 | 说明 |
|------|------|
| `check-login` | 检查当前登录状态 |
| `get-qrcode` | 获取二维码进行扫码登录 |
| `wait-login` | 等待用户扫码完成登录 |
| `send-code` | 发送短信验证码 |
| `verify-code` | 校验短信验证码 |
| `list-accounts` | 列出已保存账号 |
| `add-account` | 添加新账号 |
| `remove-account` | 删除账号 |
| `set-default-account` | 设置默认使用账号 |

### 🔍 搜索 / 内容发现
| 命令 | 说明 |
|------|------|
| `search-videos` | 按关键词搜索作品 |
| `get-video-detail` | 根据作品 ID 获取详细信息 |

### 📝 图文发布
| 命令 | 说明 |
|------|------|
| `fill-publish-image` | 填写图文发布表单及上传配图 |
| `select-music` | 选择背景音乐 |
| `click-publish` | 执行发布操作 |

### ❤️ 基础互动
| 命令 | 说明 |
|------|------|
| `like-video` | 给作品点赞 |
| `favorite-video` | 收藏作品 |
| `share-video` | 分享作品链接 |

---

## 💻 运行机制

- 默认优先使用 **headless** 模式运行。
- 只有检测到**验证码 / 身份验证 / 风控页**时，才切到 **headed** 模式，请用户手动完成验证。
- 图文发布默认要求：**竖版配图 + 发布前人工复核**，避免上下留白、白条、异常元素或封面裁切问题。

---

## ⚙️ 环境要求（可让Agent根据douyin-env skill自动完成环境配置）

### 必需二进制
- `python3`
- `node`
- `npm`
- Chrome / Chromium

### 必需依赖
- Node 包：`ws`
- Python 包：`Pillow`

### 浏览器要求
浏览器需要支持 remote debugging。脚本会尝试以下名称之一：
- `google-chrome`
- `google-chrome-stable`
- `chromium`
- `chromium-browser`
- `chrome`

也可以通过环境变量指定：

```bash
CHROME_BIN=/path/to/chrome
```

---

## 📄 License

本项目采用 MIT License，欢迎自由使用和二次开发。
