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
- 导航后的短暂验证码/风控中间页会由 CLI 做有限稳定重检；切到 headed 后还会重新读取当前页面，不沿用切换前的旧风险结果。
- `logged_in: true`：可以继续。
- `logged_in: false`：进入登录流程；退出码 `1` 不是程序崩溃。
- `action: risk_recovered_after_headed_switch`、`risk_recovered: true` 且 `logged_in: true`：临时风险状态已经消失，直接继续，不要请用户验证。
- `needs_user_verification: true`：浏览器已切为 headed 或已停在验证页，请用户人工处理，不要绕过或连续重试。

## 二维码登录

1. 获取二维码：

```bash
python "{baseDir}/../../scripts/cli.py" get-qrcode
```

2. 从 JSON 的 `qrcode_path` 读取本地图片并展示给用户，不输出二维码内容到日志。二维码使用唯一私有临时目录；扫码结束或二维码过期后删除该文件及其空目录。
3. 用户扫码后单次等待：

```bash
python "{baseDir}/../../scripts/cli.py" wait-login
```

`wait-login` 最多等待 120 秒。超时后重新获取二维码，不要高频轮询。

## 短信验证码登录

普通手机号页先取得用户明确提供的中国大陆手机号：

```bash
python "{baseDir}/../../scripts/cli.py" send-code --phone-stdin
```

通过进程标准输入传入一行手机号；交互终端会隐藏输入。不要把手机号拼入 shell 命令或 `echo`/`printf` 参数。普通短信登录页已由用户填写手机号时，可以不传手机号：

```bash
python "{baseDir}/../../scripts/cli.py" send-code
```

收到用户提供的 6 位验证码后提交：

```bash
python "{baseDir}/../../scripts/cli.py" verify-code --code-stdin
```

通过进程标准输入传入一行验证码。也可用 `--phone-env <变量名>` / `--code-env <变量名>` 读取工具安全注入的环境变量；变量在本进程读取后移除，stdin 为首选。旧的 `--phone` / `--code` 仅为兼容保留并发出弃用警告，仍可能出现在进程列表和命令历史中。不要在回复中重复完整手机号或验证码；不要保存这些一次性信息。出现平台验证码、安全验证或风险页面时停止，交由用户人工处理。

## 多账号

```bash
python "{baseDir}/../../scripts/cli.py" add-account --name work --description "工作号"
python "{baseDir}/../../scripts/cli.py" set-default-account --name work
python "{baseDir}/../../scripts/cli.py" update-account --name work --description "创作账号"
python "{baseDir}/../../scripts/cli.py" --account work check-login
python "{baseDir}/../../scripts/cli.py" remove-account --name work
```

每个命名账号使用独立端口和 Chrome Profile。账号名称必须是跨平台有效目录名；重复端口、大小写冲突名称和损坏配置会被拒绝。`update-account` 只修改描述，`remove-account` 只移除账号登记并保留 Profile 数据。

## 边界与失败处理

- 当前没有公开的强制退出或清除 Cookie 命令；不要承诺代替用户登出。
- Chrome 未找到时先使用 `douyin-env` 运行 `doctor`。
- 配置损坏时报告具体路径并停止，不要自动重建。
- 只有 CLI 最终返回 `needs_user_verification: true` 时，才保留可见浏览器并等待用户处理；标题或风险关键词命中本身不等于需要人工验证。
