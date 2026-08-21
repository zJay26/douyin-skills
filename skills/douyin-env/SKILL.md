---
name: douyin-env
description: 检查、安装、迁移和排查 douyin-skills 本地运行环境，包括 Python、Node.js、ws、Chrome/Chromium、图形环境和本地 Profile。用户要求安装、配置、部署、迁移、环境自检或解决依赖问题时使用。
---

# 配置 douyin-skills 环境

让本机具备运行登录、搜索、图文发布与基础互动的条件，不执行真实账号操作。

## 定位项目

- 当前子技能目录为 `{baseDir}`。
- 项目根目录为 `{baseDir}/../..`。
- CLI 为 `{baseDir}/../../scripts/cli.py`。
- 将示例中的 `python` 替换为系统可用的 `python3`（如需要）。

## 环境要求

| 组件 | 最低要求 | 用途 |
| --- | --- | --- |
| Python | 3.9+ | CLI 与页面流程 |
| Node.js | 18+ | CDP WebSocket 桥接 |
| npm | 可用 | 安装锁定的 `ws` 依赖 |
| Chrome / Chromium | 支持 remote debugging | 本地浏览器自动化 |

Python 运行时只使用标准库，不需要 Pillow，也没有字体资产依赖。

## 安装依赖

在 Skill 根目录安装仓库锁定的 Node 依赖：

```bash
npm install --prefix "{baseDir}/../.."
```

不要在未知工作目录执行全局安装，也不要删除用户现有的 Chrome Profile。

## 运行自检

```bash
python "{baseDir}/../../scripts/cli.py" doctor
```

只有当 JSON 中 `success` 为 `true` 且 `required_failures` 为空时，才报告环境已就绪。`display` 是可选项，但没有图形环境时无法在风控阶段显示浏览器供人工验证。

## Chrome 定位

CLI 会检查 PATH，以及 Windows、macOS、Linux、WSL 中的常见安装位置。仍未找到时设置：

```bash
CHROME_BIN=/absolute/path/to/chrome
```

`CHROME_BIN` 必须指向真实文件。CDP 只绑定 `127.0.0.1`。

Linux 容器以 root 运行时会按 Chrome 要求加入 `--no-sandbox`。非 root 环境不要主动关闭沙箱；只有明确了解风险时才设置 `DOUYIN_CHROME_NO_SANDBOX=1`。

## 迁移

优先让 OpenClaw 直接从 Git 安装完整仓库。手工迁移时复制整个项目，至少保留：

```text
SKILL.md
skills/
scripts/
package.json
package-lock.json
```

不要迁移 `node_modules/`、`__pycache__/`、本地日志或 `~/.douyin-skills/`。如果用户确实要迁移登录 Profile，先说明其中包含会话数据，并要求用户通过受信任的本地方式自行处理。

## 常见问题

- `ws` 缺失：在项目根目录重新运行 `npm install`，再执行 `doctor`。
- Chrome 未找到：安装 Chrome/Chromium，或设置绝对路径 `CHROME_BIN`。
- 端口被占用：如果是可用的 loopback Chrome 调试实例，CLI 会直接复用它及其登录会话；只有需要模式切换且该实例由本项目跟踪时才会重启。若端口来源不明或不可识别，关闭冲突实例或显式使用空闲 `--port`；不要终止来源不明的进程。
- 无法切换 headed：确认 Windows/macOS 桌面可用；Linux/WSLg 检查 `DISPLAY`、`WAYLAND_DISPLAY` 与 `XDG_RUNTIME_DIR`。
- 配置损坏：保留原文件并报告 `~/.douyin-skills/accounts.json` 错误，不要擅自删除账号配置。
