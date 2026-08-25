---
name: douyin-explore
description: 在抖音网页版按关键词搜索公开作品、读取 video 或 note 作品详情，并查看公开热门话题。用户要求搜索抖音、查找作品、查看公开作品详情、查看热门话题或解析抖音作品链接时使用。
---

# 搜索与查看公开作品

只使用 `python "{baseDir}/../../scripts/cli.py" <子命令>`。如果系统只有 `python3`，替换命令名。

## 前置条件

1. 根据用户指定账号传 `--account <名称>`；未指定时使用 CLI 默认账号。
2. 先运行 `check-login`。未登录时转交 `douyin-auth`。
3. 检测到 `needs_user_verification` 后停下，请用户在 headed 浏览器处理验证。

## 搜索

```bash
python "{baseDir}/../../scripts/cli.py" search-videos --keyword "关键词" --limit 7
```

- 默认返回 7 条，用户明确指定时调整，单次最多 20 条。
- 关键词为空时停止并请用户补充。
- 结果同时可能包含 `video` 与 `note`，以每项 `kind` 字段为准。
- 用标题、作者、作品类型和公开链接整理结果；缺失字段保持为空，不推测作者 ID 或互动数据。

## 读取详情

`--video-id` 兼容纯数字 ID、`douyin.com/video/...` 与 `douyin.com/note/...` 公开链接：

```bash
python "{baseDir}/../../scripts/cli.py" get-video-detail --video-id <作品ID或公开链接>
```

拒绝非 `douyin.com` 链接。根据 `content_type` 区分视频和图文；作品不存在、私密、已删除或页面结构变化时如实报告。

## 查看热门话题

```bash
python "{baseDir}/../../scripts/cli.py" get-trending-topics
```

- 读取抖音公开热门话题页，最多返回 20 条识别到的话题及摘要。
- `state: page_drift` 表示页面有内容但当前选择器没有识别出话题；不要把空结果报告为“没有热门话题”。
- 这不是用户主页抓取、评论区采集、数据分析或批量互动。

## 结果与边界

- `needs_user_verification: true`：切到人工验证流程；若 `check-login` 已返回 `risk_recovered: true`、`logged_in: true`，继续执行，不要因切换前的风险状态停下。
- `count: 0` 且 `success: true`：搜索正常但没有结果，可建议更换关键词。
- 不执行用户主页批量抓取、评论区全量采集、高级筛选、话题历史趋势分析或数据分析。
- 不为补齐作者 ID 逐条打开结果详情；保持搜索流程轻量，避免额外请求。
