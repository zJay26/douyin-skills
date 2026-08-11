# 参与贡献

感谢你帮助改进 douyin-skills。提交前请先确认改动面向真实用户问题，并保持 CLI、Skill 文档和安全边界一致。

## 本地开发

需要 Python 3.9+、Node.js 18+、npm 和 Chrome/Chromium。

```bash
npm install
python scripts/cli.py doctor
python -m unittest discover -s tests/python -v
npm run check
npm test
```

代码风格检查使用 Ruff 0.16.2：

```bash
python -m pip install ruff==0.16.2
ruff check scripts tests/python
ruff format --check scripts tests/python
```

## 提交建议

1. 一个提交只解决一类问题，使用清楚的命令式提交信息，例如 `fix: reject unsafe publish retry`。
2. 行为变化必须补测试，并同步对应的 `SKILL.md` 与 README。
3. 页面选择器变化要说明验证过的页面、Chrome 版本和仍未验证的场景。
4. 不提交 `node_modules/`、`__pycache__/`、Cookie、验证码、二维码、账号配置或 Chrome Profile。
5. 不加入验证码绕过、批量刷量、养号或未经授权账号操作。

## Pull Request

PR 中请写明用户问题、方案、验证证据与剩余边界。真实页面截图和日志必须脱敏。安全漏洞请按 [SECURITY.md](SECURITY.md) 私下报告。
