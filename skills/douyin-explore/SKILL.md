---
name: douyin-explore
description: |
  抖音内容发现技能。支持搜索视频、查看作品详情。
  当用户要求搜索抖音、查看视频详情时触发。
---

# 抖音搜索与探索

只处理当前已经稳定实现的发现能力。

## 🔒 技能边界（强制）

**所有搜索和浏览操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`。
- **忽略其他项目**：执行时必须只使用本项目脚本。
- **禁止外部工具**：不得调用 MCP 工具、Go 命令行工具，或任何非本项目实现。
- **完成即止**：搜索或浏览结束后直接汇报结果。

**本技能允许使用的 CLI 子命令：**

| 子命令 | 用途 |
|--------|------|
| `list-feeds` | 获取首页推荐 Feed |
| `search-videos` | 关键词搜索视频 |
| `get-video-detail` | 获取作品详情 |
| `trending-topics` | 获取热门话题榜单 |

## 账号选择（前置步骤）

每次 skill 触发后，先运行：

```bash
python scripts/cli.py list-accounts
```

根据返回的 `count`：
- **0 个命名账号**：直接使用默认账号。
- **1 个命名账号**：直接使用该账号。
- **多个命名账号**：询问用户选择哪个账号。

## 必做约束

- 所有操作需要已登录的 Chrome 浏览器。
- 做“搜索 / 探索”类任务时，默认返回 7 条内容；用户明确指定数量时才覆盖。
- 结果应结构化呈现，突出标题、作者、链接、互动数据。
- CLI 输出为 JSON 格式。
- 如果搜索页检测到验证码、身份验证或风控页，必须**立即重新以有头模式执行同一步**；在 WSLg / Linux 下显式附带：`DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 FORCE_HEADED=1`；如果已经是有头模式，则停在可见窗口并请求用户人工处理后再继续。

## 工作流程

### 主页作品反查（补充）

当用户要求对**刚发布的作品**继续做点赞、收藏或取链接，而搜索暂时搜不到时：

1. 打开 `https://www.douyin.com/user/self?showTab=post`
2. 在作品列表里找到对应文案/标题
3. 从作品卡片上的公开链接提取真实 `note_id` / `video_id`
4. 再交给 `douyin-interact` 执行互动

### 首页 Feed

```bash
python scripts/cli.py list-feeds
```

### 搜索视频

```bash
python scripts/cli.py search-videos --keyword "关键词" --limit 7
```

### 获取作品详情

```bash
python scripts/cli.py get-video-detail --video-id VIDEO_ID
```

### 获取热门话题

```bash
python scripts/cli.py trending-topics
```

## 明确不支持

以下能力不再属于本技能范围：
- 用户主页抓取
- 高级搜索筛选参数
- 评论区全量抓取
- 账号/视频数据分析

## 失败处理

- **未登录**：提示先执行登录。
- **搜索无结果**：建议更换关键词。
- **作品不可访问**：提示可能已删除或私密。
- **网络超时**：提示稍后重试。
