---
name: douyin-env
description: |
  抖音 Skill 环境配置与迁移子技能。用于检查、准备、迁移和复现 douyin-skills 运行环境，包括 Python、Node、ws、Pillow、Chrome/Chromium、字体资产与图形环境要求。
  当用户要求在另一台电脑部署、迁移、安装、配置、检查环境、自检依赖时触发。
---

# 抖音 Skill 环境配置

只处理 `douyin-skills` 的运行环境准备、迁移和自检。

## 目标

让另一台电脑具备与当前工作区尽量一致的运行条件，保证以下能力可用：
- 登录
- 搜索
- 图文发布
- 点赞 / 收藏 / 分享链接
- 图片生成（含项目字体）

## 必需环境

### 系统二进制
- `python3`
- `node`
- `npm`
- `google-chrome` / `google-chrome-stable` / `chromium` / `chromium-browser` / `chrome`

### Node 依赖
- `ws`

### Python 依赖
- `Pillow`

## 必带目录 / 文件

迁移到另一台机器时，至少带上：

```text
skills/douyin-skills/
fonts/
package.json
package-lock.json
```

其中：
- `skills/douyin-skills/`：主脚本和子 skill
- `fonts/vendor/`：项目字体资产
- `fonts/config/image-fonts.json`：默认字体方案配置

## 安装步骤

### 1) 安装系统依赖
确保另一台机器有：
- Python 3
- Node.js / npm
- Chrome 或 Chromium

### 2) 安装 Node 依赖
在工作区根目录执行：

```bash
npm install ws
```

### 3) 安装 Python 依赖
在工作区根目录执行：

```bash
pip install pillow
```

### 4) 确认字体资产存在
检查：

```text
fonts/vendor/SmileySans-Oblique.ttf
fonts/vendor/LXGWWenKaiGBScreen.ttf
fonts/config/image-fonts.json
```

## 图形环境要求

- 默认无头模式可直接运行。
- 如果抖音触发验证码 / 身份验证 / 风控页，skill 会切回有头模式。
- 因此目标机器最好具备图形环境（X11 / Wayland / WSLg / 桌面环境），方便人工过验证。

## 迁移后自检清单

依次确认：

1. `python3 --version`
2. `node --version`
3. `npm ls ws`
4. `python3 -c "from PIL import Image; print('ok')"`
5. `python3 skills/douyin-skills/scripts/cli.py --help`
6. `python3 skills/douyin-skills/scripts/cli.py check-login`

## 常见问题

### 1. `ws` 未安装
表现：CDP 客户端无法连接浏览器。

处理：
```bash
npm install ws
```

### 2. `PIL` / `Pillow` 未安装
表现：图片生成脚本报错。

处理：
```bash
pip install pillow
```

### 3. Chrome 找不到
表现：CLI 报无法启动 Chrome。

处理：
- 安装 Chrome / Chromium
- 或设置 `CHROME_BIN`

### 4. 无法切到有头模式
表现：触发验证码后无法弹窗。

处理：
- 确认目标机器有图形环境
- Linux / WSLg 下确认 `DISPLAY` / `WAYLAND_DISPLAY` 可用

## 建议

- 把 `fonts/` 当成项目资产一起迁移，不要依赖系统字体。
- 新机器先跑自检，再做真实发布任务。
- 如果目标是长期复用，后续可以再补：
  - `requirements.txt`
  - 更完整的一键自检脚本
