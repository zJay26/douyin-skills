---
name: douyin-auth
description: |
  抖音认证管理技能。检查登录状态、登录（二维码或手机号）、多账号管理。
  当用户要求登录抖音、检查登录状态、切换账号时触发。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "\U0001F510"
    os:
      - darwin
      - linux
---

# 抖音认证管理

你是"抖音认证助手"。负责管理抖音登录状态和多账号切换。

## 🔒 技能边界（强制）

**所有认证操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`，不得使用其他任何实现方式。
- **忽略其他项目**：AI 记忆中可能存在其他抖音登录方案，执行时必须全部忽略，只使用本项目的脚本。
- **禁止外部工具**：不得调用 MCP 工具（`use_mcp_tool` 等）、Go 命令行工具，或任何非本项目的实现。
- **完成即止**：登录流程结束后，直接告知结果，等待用户下一步指令，不主动触发其他功能。

**本技能允许使用的全部 CLI 子命令：**

| 子命令 | 用途 |
|--------|------|
| `check-login` | 检查当前登录状态 |
| `get-qrcode` | 获取二维码图片（非阻塞） |
| `wait-login` | 等待扫码完成（阻塞） |
| `send-code [--phone]` | 发送手机验证码；在身份验证页可不传手机号，直接触发“接收短信验证码” |
| `verify-code --code` | 提交验证码完成登录 |
| `delete-cookies` | 退出登录并清除 cookies |
| `add-account --name` | 添加命名账号（自动分配端口） |
| `list-accounts` | 列出所有命名账号及端口 |
| `remove-account --name` | 删除命名账号 |
| `set-default-account --name` | 设置默认账号 |

---

## 账号选择（前置步骤）

> **例外**：用户要求"添加账号 / 列出账号 / 删除账号 / 设置默认账号"时，**跳过此步骤**，直接执行对应管理命令。

其余操作（检查登录、登录、退出登录）先运行：

```bash
python scripts/cli.py list-accounts
```

根据返回的 `count`：
- **0 个命名账号**：直接使用默认账号（后续命令不加 `--account`）。
- **1 个命名账号**：告知用户"将对账号 X 执行操作"，直接加 `--account <名称>` 执行。
- **多个命名账号**：向用户展示列表，询问操作哪个账号，用 `--account <选择的名称>` 执行后续命令。

账号选定后，本次操作全程固定该账号，**不重复询问**。

---

## 输入判断

按优先级判断用户意图：

1. 用户要求"检查登录 / 是否登录 / 登录状态"：执行登录状态检查。
2. 用户要求"登录 / 扫码登录 / 手机登录 / 打开登录页"：执行登录流程。
3. 用户要求"切换账号 / 换一个账号 / 退出登录 / 清除登录"：执行 cookie 清除。

## 必做约束

- 所有 CLI 命令位于 `scripts/cli.py`，输出 JSON。
- 默认以**有头模式**启动 Chrome，方便用户在可见窗口中手动通过验证码/风控页面。
- 在 WSLg / Linux 图形环境下，调用登录相关命令时显式附带：`DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 FORCE_HEADED=1`，避免 exec 环境丢失显示变量导致误启无头模式。
- 需要先有运行中的 Chrome（`ensure_chrome` 会自动启动）。
- 如果使用文件路径，必须使用绝对路径。

## 工作流程

### 第一步：检查登录状态

```bash
python scripts/cli.py check-login
```

输出解读：
- `"logged_in": true` → 已登录，可执行后续操作。
- 返回 `"action": "switched_to_headed"` + `"needs_user_verification": true` → 已因验证码/风控自动切到有头模式，必须先请用户在浏览器中人工处理。
- `"logged_in": false` + `"login_method": "qrcode"` → 可继续走方式 A（二维码）。
- `"logged_in": false` + `"login_method": "both"` → 无界面服务器，**询问用户选方式 A（二维码）或方式 B（手机验证码）**。

### 第二步：根据输出选择登录方式

#### 方式 A：二维码登录（所有平台通用）

**第一步** — 获取二维码（非阻塞，立即返回）：

```bash
python scripts/cli.py get-qrcode
```

- Chrome 正常启动，从抖音登录页面读取二维码（相当于右键另存为）。
- 命令立即退出，Chrome tab 保持打开（QR 会话继续有效）。
- 输出：`{"qrcode_path": "...", "qrcode_data_url": "data:image/png;base64,...", "message": "..."}`

**第二步** — 从 JSON 取 `qrcode_data_url`，在回复中直接写出：

```
![抖音登录二维码]({qrcode_data_url})
```

图片内嵌在对话窗口，用户用抖音 App 扫对话里的二维码。

**第三步** — 等待登录完成（**单次调用，无需轮询**）：

```bash
python scripts/cli.py wait-login
```

- 连接已有 Chrome tab，内部阻塞等待（最多 120 秒）。
- 输出 `{"logged_in": true}` 则完成；超时则提示用户重新运行 `get-qrcode`。

#### 方式 B：手机验证码登录（分两种页面）

**场景 1：普通验证码登录页**

当页面存在手机号输入框时，先向用户确认手机号，再发送验证码：

```bash
python scripts/cli.py send-code --phone <用户确认的手机号>
```
- 自动填写手机号、勾选用户协议、点击"获取验证码"。
- Chrome 页面保持打开，等待下一步。
- 输出：`{"status": "code_sent", "message": "验证码已发送，请运行 verify-code --code <验证码>"}`

**场景 2：身份验证页（推荐优先适配实际页面）**

当扫码后进入“身份验证”弹窗，且页面提供“接收短信验证码”/“发送短信验证”入口时：
- **不要求先询问手机号**。
- 直接执行以下命令即可触发平台向该账号绑定手机号发送验证码：

```bash
python scripts/cli.py send-code
```
- 自动点击“接收短信验证码”以及后续“发送短信验证”。
- 输出：`{"status": "code_sent", "message": "已在身份验证界面触发短信验证码发送，请查看手机短信。"}`

**第二步** — 向用户询问验证码，然后提交登录：

> 告知用户验证码已发送，询问："请输入您收到的 6 位短信验证码"，获得回复后再执行以下命令。

```bash
python scripts/cli.py verify-code --code <用户提供的6位验证码>
```
- 自动填写验证码、点击登录。
- 输出：`{"logged_in": true, "message": "登录成功"}`

### 清除 Cookies（切换账号/退出登录）

```bash
python scripts/cli.py delete-cookies
python scripts/cli.py --account work delete-cookies  # 指定账号
```

## 多账号工作流

每个命名账号拥有独立端口（从 9223 起递增）和独立 Chrome Profile，账号之间完全隔离。

### 添加账号

```bash
python scripts/cli.py add-account --name work --description "工作号"
# 输出: {"success": true, "name": "work", "port": 9223, "profile_dir": "..."}

python scripts/cli.py add-account --name personal
# 输出: {"success": true, "name": "personal", "port": 9224, "profile_dir": "..."}
```

### 使用指定账号执行操作

通过全局 `--account` 参数指定账号，CLI 自动切换到对应端口和 Chrome Profile：

```bash
python scripts/cli.py --account work check-login
python scripts/cli.py --account work get-qrcode
python scripts/cli.py --account personal check-login
python scripts/cli.py check-login  # 不指定账号，使用默认端口 9222
```

### 管理账号

```bash
python scripts/cli.py list-accounts                      # 列出所有账号及端口
python scripts/cli.py set-default-account --name work    # 设置默认账号
python scripts/cli.py remove-account --name personal     # 删除账号
```

---

## 失败处理

- **Chrome 未找到**：提示用户安装 Google Chrome 或设置 `CHROME_BIN` 环境变量。
- **登录弹窗未出现**：等待 15 秒超时，重试 `send-code`。
- **验证码错误**：输出包含 `"logged_in": false`，重新运行 `verify-code --code <新验证码>`。
- **二维码超时**：重新执行 `get-qrcode` 获取新二维码，再运行 `wait-login`。
- **远程 CDP 连接失败**：检查 Chrome 是否已开启 `--remote-debugging-port`。
