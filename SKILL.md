---
name: douyin-skills
description: 抖音网页版与创作者中心的本地自动化技能包入口。用于组合登录、搜索、图文发布、点赞、收藏、分享链接，或解释整体能力、安全边界与多步骤流程；单一任务优先使用对应的 douyin-* 子技能。
---

# 抖音自动化技能包

使用本项目的本地 CLI 驱动本机 Chrome，处理登录、内容发现、图文发布和基础互动。

## 执行入口

- 将 `{baseDir}` 视为当前 Skill 的绝对目录。
- 只通过 `python "{baseDir}/scripts/cli.py" <子命令>` 操作抖音。
- 如果系统只有 `python3`，将示例中的 `python` 替换为 `python3`。
- 首次使用或环境变化后先运行：

```bash
python "{baseDir}/scripts/cli.py" doctor
```

CLI 始终输出 JSON。根据字段判断结果，不要只看进程退出码或按钮是否被点击。

在依赖特定字段前运行以下命令读取运行时与结果契约版本：

```bash
python "{baseDir}/scripts/cli.py" version
```

解析规则、确认/未确认状态和退出码见 `{baseDir}/docs/RESULT_CONTRACT.md`。

## 路由任务

| 用户意图 | 使用子技能 |
| --- | --- |
| 检查登录、扫码、短信验证、多账号 | `douyin-auth` |
| 安装、迁移、依赖检查 | `douyin-env` |
| 搜索、读取公开作品详情 | `douyin-explore` |
| 图文表单、音乐、发布 | `douyin-publish` |
| 点赞、收藏、获取分享链接 | `douyin-interact` |

多步骤请求按 `认证 → 内容准备/搜索 → 发布或互动 → 结果确认` 的顺序组合子技能。

## 共同约束

1. 将实际抖音页面操作限制在本项目 CLI；可以使用普通文件或图片工具准备、检查素材，但不要换用另一套抖音自动化实现。
2. 只连接 loopback Chrome 调试地址，不向局域网或公网暴露 CDP。
3. 默认使用 headless。检测到验证码、身份验证或风控页后，让 CLI 切换到 headed，停下并请用户人工处理；不要尝试绕过验证。
4. 在任何会改变账号状态的操作前确认目标账号与目标作品。用户明确提出“点赞/收藏/发布该内容”可视为本次操作授权。
5. 发布前必须检查标题、正文、图片和音乐，并执行 `validate-publish`。最终点击必须显式传 `--confirm`。
6. 发布返回 `status: publish_clicked_unconfirmed` 时，不要重试；先去作品管理确认，避免重复发布。
7. 点赞和收藏在部分页面只能确认“按钮已点击”，不能稳定确认最终状态。`state_verified: false` 时如实说明，不要自动重复点击。
8. 保持合理操作频率，不执行批量养号、刷量或规避平台限制的流程。

## 账号规则

- 不指定 `--account` 时，CLI 会使用已设置的默认命名账号；没有命名账号时使用端口 `9222` 的默认 Profile。
- 用户明确指定账号时，在子命令前传 `--account <名称>`。
- 不要同时传入冲突的 `--account` 与 `--port`。
- Chrome Profile 与账号配置保存在本机 `~/.douyin-skills/`；不要提交到仓库或上传给第三方。

## 当前公开命令

- 运行时：`version`
- 环境：`doctor`
- 认证：`check-login`、`get-qrcode`、`wait-login`、`send-code`、`verify-code`
- 账号：`list-accounts`、`add-account`、`remove-account`、`set-default-account`
- 发现：`search-videos`、`get-video-detail`
- 发布：`fill-publish-image`、`select-music`、`validate-publish`、`click-publish`
- 互动：`like-video`、`favorite-video`、`share-video`

## 不承诺的能力

不要承诺评论、回复评论、私信、视频发布、草稿、定时发布、数据分析、用户主页批量抓取、批量互动或完整运营流水线。

本项目与抖音及字节跳动无隶属或官方合作关系。仅操作用户有权使用的账号与内容，并遵守适用法律和平台规则。
