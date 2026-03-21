<div align="center">

# douyin-skills

**抖音网页自动化Skills**  
**支持登录、搜索、图文发布、点赞、收藏、分享，可作为 OpenClaw Skill 集成使用。**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-required-43853d?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Compatible-6f42c1?style=for-the-badge)](https://docs.openclaw.ai)

</div>

---

## 项目简介

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

## 安装

### 方法一：下载 ZIP 安装（推荐）

适用于 OpenClaw 及所有支持 `SKILL.md` 的 Agent 平台。

1. 在 GitHub 仓库页面点击 **Code → Download ZIP**，下载项目压缩包。
2. 解压后，将 `douyin-skills/` 文件夹放到你的 Agent skills 目录下。

```text
# OpenClaw 示例
<openclaw-project>/skills/douyin-skills/

# Claude Code 示例
<your-project>/.claude/skills/douyin-skills/
```

### 方法二：Git 克隆安装

如果你希望后续通过 `git pull` 持续更新，直接克隆到 skills 目录即可：

```bash
# OpenClaw 示例
git clone <your-repo-url> <openclaw-project>/skills/douyin-skills

# Claude Code 示例
git clone <your-repo-url> <your-project>/.claude/skills/douyin-skills
```

### 方法三：作为独立脚本工程使用

如果你不准备把它作为 Skill 目录接入，也可以直接把这个仓库当成普通脚本项目运行：

```bash
git clone <your-repo-url>
cd douyin-skills
```

---

## 设计取向

项目采用较小的公开命令面，重点放在以下几点：

- 以高频场景为主，避免一次性暴露过多不稳定能力
- 保持命令边界清晰，降低维护成本
- 将运行依赖、发布流程、互动流程拆分为独立子 Skill，便于复用与迁移
- 在网页结构波动较大的场景下，优先保留可维护性而非追求表面上的功能覆盖率

---

## 当前能力

### 1）认证与账号管理
- 检查登录状态
- 二维码登录
- 手机验证码登录
- 多账号管理
- 默认账号切换

### 2）搜索与内容发现
- 按关键词搜索作品
- 根据作品 ID 获取详情

### 3）图文发布
- 填写图文发布表单
- 选择音乐
- 发布图文

### 4）基础互动
- 点赞
- 收藏
- 分享链接

### 5）环境配置
- 说明运行依赖
- 说明迁移到另一台电脑时需要准备什么
- 说明如何做环境自检

---

## 未来拓展

暂不支持以下能力：

- 评论
- 回复评论
- 视频发布
- 定时发布
- 数据分析面板
- 复杂批量运营
- 完整创作者中心工作流自动化

---

## 仓库结构

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

## 当前保留命令

### 认证 / 账号
- `check-login`
- `get-qrcode`
- `wait-login`
- `send-code`
- `verify-code`
- `list-accounts`
- `add-account`
- `remove-account`
- `set-default-account`

### 搜索发现
- `search-videos`
- `get-video-detail`

### 图文发布
- `fill-publish-image`
- `select-music`
- `click-publish`

### 基础互动
- `like-video`
- `favorite-video`
- `share-video`

这就是当前项目对外保留的核心命令面。

---

## 运行机制

### 默认无头模式
项目默认优先使用 **headless** 模式运行，以减少干扰并提升自动化流畅度。

### 遇到验证时自动切回有头模式
如果检测到：
- 验证码
- 身份验证
- 风控页

就会切回 **headed** 模式，请用户手动完成验证。

这样做的原因很现实：
- 抖音在无头和有头模式下行为不完全一致
- 搜索页、详情页、创作者中心页并不统一
- 新发布作品也不一定能立刻在公开搜索里找到

所以这个项目的原则是：

> **优先让高频流程稳定工作，而不是为了“全自动”硬上。**

---

## 环境要求

### 必需二进制
- `python3`
- `node`
- `npm`
- Chrome / Chromium

### 必需依赖
- Node 包：`ws`
- Python 包：`Pillow`（如果你会用本地图片生成脚本）

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

## 安装方式

### 1）克隆仓库

```bash
git clone <your-repo-url>
cd douyin-skills
```

### 2）安装 Node 依赖

```bash
npm install ws
```

### 3）安装 Python 依赖

```bash
pip install pillow
```

---

## 快速开始

### 检查登录状态

```bash
python3 scripts/cli.py check-login
```

### 获取登录二维码

```bash
python3 scripts/cli.py get-qrcode
```

### 等待登录完成

```bash
python3 scripts/cli.py wait-login
```

### 搜索视频

```bash
python3 scripts/cli.py search-videos --keyword "AI焦虑" --limit 7
```

### 获取作品详情

```bash
python3 scripts/cli.py get-video-detail --video-id 7619615485310668078
```

### 填写图文发布表单

```bash
python3 scripts/cli.py fill-publish-image \
  --title "你的标题" \
  --desc-file /abs/path/desc.txt \
  --images /abs/path/pic1.jpg /abs/path/pic2.jpg
```

### 选择音乐

```bash
python3 scripts/cli.py select-music
```

### 发布

```bash
python3 scripts/cli.py click-publish
```

### 点赞 / 收藏 / 分享

```bash
python3 scripts/cli.py like-video --video-id 7619615485310668078
python3 scripts/cli.py favorite-video --video-id 7619615485310668078
python3 scripts/cli.py share-video --video-id 7619615485310668078
```

---

## 发布相关说明

当前图文发布流程有意保持简单：

1. 填表
2. 选音乐
3. 看页面状态是否正常
4. 发布

之前项目里曾经有更复杂的校验思路，但最后没有继续保留为正式公开命令。
原因很简单：

> 页面检查可以辅助判断，但不能把它包装成百分百可靠的“正式校验器”。

---

## 关于“刚发布的作品”

刚发完作品后，不要默认认为搜索立刻能搜到它。

更可靠的路径是：
1. 打开自己的抖音主页
2. 从作品列表里找到刚发的图文
3. 提取真实公开 `note` / `video` 链接
4. 再去做点赞、收藏、分享等互动

这一点在实际使用里非常重要。

---

## 既可以单独用，也可以接入 OpenClaw

这个仓库本身就是一套可以独立维护的脚本与 Skill 结构。

### 如果你单独使用
你可以直接运行：
- `python3 scripts/cli.py ...`

### 如果你接入 OpenClaw
它也已经按 OpenClaw Skill 的结构组织好了：
- 主入口：`SKILL.md`
- 子技能：
  - `skills/douyin-auth/`
  - `skills/douyin-env/`
  - `skills/douyin-explore/`
  - `skills/douyin-interact/`
  - `skills/douyin-publish/`

所以它并不只是一个“只能给 OpenClaw 用的内部文件夹”，而是：

> **既能独立运行，也能无缝作为 OpenClaw Skill 使用。**

---

## 局限性

这是一个基于真实网站页面的自动化项目，不是官方 API。

因此它天然会受这些变化影响：
- DOM 结构变化
- 反爬/风控策略变化
- 登录流程变化
- 创作者中心上传流程变化
- note / video 页面布局变化

所以更准确的理解应该是：

> **这是一个持续维护的自动化工具，而不是一个稳定不变的平台接口。**

---

## 后续值得继续做的方向

可以继续增强，但应该继续保持克制：
- 更完整的环境自检脚本
- 更明确的一键安装流程
- 更稳的发布状态识别
- 更稳的创作者中心异常恢复逻辑

不是所有“能做”的东西都应该成为公开命令。
对外暴露的能力，应该一直保持高门槛。

---

## 贡献建议

如果你想继续扩展这个项目，建议遵守同一个原则：

- 命令面尽量小
- 不要把实验功能包装成稳定能力
- 宁可少一点，也不要误导用户
- 先能维护，再谈扩展

这个项目最值钱的地方，不是功能堆得多，而是：

> **收得住。**

---

## License

本项目采用 MIT License。  
详见 [LICENSE](./LICENSE)。
