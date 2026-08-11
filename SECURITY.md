# 安全政策

## 支持范围

安全修复以 `main` 分支最新版本为准。旧提交不会单独维护安全补丁。

## 私下报告漏洞

请使用 GitHub 的 [Private vulnerability reporting](https://github.com/zJay26/douyin-skills/security/advisories/new)，不要公开创建包含利用细节的 Issue。

报告中请包含受影响版本、复现条件、潜在影响和建议修复方式。请勿附带真实 Cookie、手机号、验证码、二维码、账号配置或 Chrome Profile；如需示例，请使用完全脱敏的数据。

## 项目安全边界

- Chrome DevTools Protocol 仅绑定 `127.0.0.1`。
- 登录与账号数据保存在用户本机，不应提交到仓库或发送给第三方。
- 验证码与风控必须由用户在可见浏览器中人工处理。
- 发布需要显式确认；结果未确认时不得自动重试。
- 本项目不接受绕过平台限制、批量刷量或未经授权操作账号的功能。

一般功能问题请使用公开 Issue，并先移除所有敏感信息。
