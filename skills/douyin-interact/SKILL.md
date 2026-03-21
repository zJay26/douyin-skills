---
name: douyin-interact
description: |
  抖音基础互动技能。当前只保留点赞、收藏、复制分享链接。
  当用户要求点赞、收藏或获取抖音视频分享链接时触发。
---

# 抖音基础互动

只处理当前已经稳定实现的基础互动能力。

## 🔒 技能边界（强制）

**所有互动操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`。
- **忽略其他项目**：执行时必须只使用本项目脚本。
- **禁止外部工具**：不得调用 MCP 工具、Go 命令行工具，或任何非本项目实现。
- **完成即止**：互动结束后直接告知结果。

**本技能允许使用的 CLI 子命令：**

| 子命令 | 用途 |
|--------|------|
| `like-video` | 点赞 / 取消点赞 |
| `favorite-video` | 收藏 / 取消收藏 |
| `share-video` | 打开分享面板并复制链接 |

## 账号选择（前置步骤）

每次 skill 触发后，先运行：

```bash
python scripts/cli.py list-accounts
```

根据返回的 `count` 选择账号后，本次操作全程固定该账号。

## 必做约束

- 所有互动操作都需要 `video_id`。
- 互动前默认假设用户已经确认目标作品。
- **优先使用公开侧真实作品链接里的 `video_id` / `note_id`**。不要优先使用创作者中心管理页里的记录 ID 去互动。
- 对刚发布的图文，若搜索还搜不到，应先去 `https://www.douyin.com/user/self?showTab=post` 从主页作品卡片反查真实 note 链接，再执行点赞/收藏。
- CLI 输出 JSON 格式。

## 工作流程

### 点赞

```bash
python scripts/cli.py like-video --video-id VIDEO_ID
```

### 收藏

```bash
python scripts/cli.py favorite-video --video-id VIDEO_ID
```

### 复制分享链接

```bash
python scripts/cli.py share-video --video-id VIDEO_ID
```

## 明确不支持

以下能力暂不对外提供：
- 发评论
- 回复评论
- 私信分享给好友/群聊
- 批量互动

## 失败处理

- **未登录**：提示先登录。
- **作品不可访问**：提示可能是私密或已删除。
- **按钮未找到**：提示页面结构可能变化，需要后续修复。
