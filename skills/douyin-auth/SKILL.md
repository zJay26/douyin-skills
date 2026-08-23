---
name: douyin-auth
description: 管理抖音网页版登录状态、二维码登录、短信验证码登录和本地多账号 Profile。用户要求登录、检查登录状态、添加或切换账号时使用。
---

# 管理抖音登录与账号

只使用 `python "{baseDir}/../../scripts/cli.py" <子命令>`。如果系统只有 `python3`，替换命令名。不要使用其他抖音登录工具。

## 先确认账号

用户指定账号时，在子命令前加入 `--account <名称>`。用户未指定时，CLI 自动使用默认命名账号；需要展示或切换账号时运行：

```bash
python "{baseDir}/../../scripts/cli.py" list-accounts
```

多个账号且用户意图不明确时，展示名称和描述并询问一次。选定后，本次流程保持同一账号。

## 检查状态

```bash
python "{baseDir}/../../scripts/cli.py" check-login
```

- CLI 会优先复用已有的本地 Chrome 调试实例和其中的登录会话；已有 headed Chrome 不会因为默认模式偏好被重启。
- 导航后的短暂验证码/风控中间页会由 CLI 做有限稳定重检；若随后恢复到已登录页，可继续使用，不需要用户重复验证。
- `logged_in: true`：可以继续。
- `logged_in: false`：进入登录流程；退出码 `1` 不是程序崩溃。
- `needs_user_verification: true`：浏览器已切为 headed 或已停在验证页，请用户人工处理，不要绕过或连续重试。

## 二维码登录

1. 获取二维码：

```bash
python "{baseDir}/../../scripts/cli.py" get-qrcode
```

2. 将 JSON 的 `qrcode_data_url` 作为图片展示给用户，不输出到公开日志。
3. 用户扫码后单次等待：

```bash
python "{baseDir}/../../scripts/cli.py" wait-login
```

`wait-login` 最多等待 120 秒。超时后重新获取二维码，不要高频轮询。

## 短信验证码登录

普通手机号页先取得用户明确提供的中国大陆手机号：

```bash
python "{baseDir}/../../scripts/cli.py" send-code --phone <手机号>
```

身份验证页已有绑定手机号入口时，不传手机号：

```bash
python "{baseDir}/../../scripts/cli.py" send-code
```

收到用户提供的 6 位验证码后提交：

```bash
python "{baseDir}/../../scripts/cli.py" verify-code --code <6位验证码>
```

不要在回复中重复完整手机号或验证码；不要保存这些一次性信息。

## 多账号

```bash
python "{baseDir}/../../scripts/cli.py" add-account --name work --description "工作号"
python "{baseDir}/../../scripts/cli.py" set-default-account --name work
python "{baseDir}/../../scripts/cli.py" --account work check-login
python "{baseDir}/../../scripts/cli.py" remove-account --name work
```

每个命名账号使用独立端口和 Chrome Profile。账号名称不能包含路径分隔符。`remove-account` 只移除账号登记，不承诺删除 Profile 数据。

## 边界与失败处理

- 当前没有公开的强制退出或清除 Cookie 命令；不要承诺代替用户登出。
- Chrome 未找到时先使用 `douyin-env` 运行 `doctor`。
- 配置损坏时报告具体路径并停止，不要自动重建。
- 风控页出现时保留可见浏览器，等待用户处理后再重试当前步骤。
