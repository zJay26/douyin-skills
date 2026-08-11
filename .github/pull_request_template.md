## 改动说明

说明用户问题、解决方式和刻意没有覆盖的边界。

## 验证

- [ ] `python -m unittest discover -s tests/python -v`
- [ ] `npm test`
- [ ] `npm run check`
- [ ] `ruff check scripts tests/python`
- [ ] `ruff format --check scripts tests/python`

如涉及真实页面，请补充浏览器版本、账号状态、页面结果与脱敏截图；不要上传 Cookie、验证码、二维码或 Chrome Profile。

## 安全检查

- [ ] 没有降低 loopback、人工验证、发布确认或操作频率限制
- [ ] 没有提交密钥、会话数据、手机号或本地 Profile
- [ ] 文档与实际 CLI 行为一致
