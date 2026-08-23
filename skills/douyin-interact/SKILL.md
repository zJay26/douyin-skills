---
name: douyin-interact
description: 对明确指定的抖音公开 video 或 note 作品执行一次点赞、收藏或评论，或返回分享链接。用户要求点赞、收藏、评论、取消相应状态或获取抖音作品链接时使用。
---

# 执行基础互动

只使用 `python "{baseDir}/../../scripts/cli.py" <子命令>`。如果系统只有 `python3`，替换命令名。

## 前置确认

1. 根据用户指定账号传 `--account <名称>`，并检查登录状态。
2. 确认唯一目标作品。接受纯数字 ID、`douyin.com/video/...` 或 `douyin.com/note/...` 公开链接。
3. 对刚发布的作品优先使用主页作品卡片中的公开链接，不使用创作者中心内部记录 ID。
4. 不批量互动，不连续重复同一操作。

## 点赞

```bash
python "{baseDir}/../../scripts/cli.py" like-video --video-id <作品ID或公开链接>
```

网页按钮可能是切换开关。返回 `state_verified: false` 时，只能报告“已点击点赞按钮，最终状态未稳定确认”；不要声称一定已点赞或取消，也不要自动再点一次。

## 收藏

```bash
python "{baseDir}/../../scripts/cli.py" favorite-video --video-id <作品ID或公开链接>
```

同样按 `state_verified` 解释结果。按钮已点击但状态未确认时，交给用户在页面核对。

- `state: already_active` 表示目标状态本来就已激活，CLI 没有再次点击。
- `state_verified: true` 表示页面暴露了明确的激活/未激活证据；不要把一次普通点击自动等同于最终状态。

## 只读核对点赞与收藏状态

```bash
python "{baseDir}/../../scripts/cli.py" get-interaction-state --video-id <作品ID或公开链接>
```

- 该命令只读取当前按钮状态，不点击切换控件。
- `state_verified: true` 且 `state: active` / `inactive` 表示页面提供了明确状态证据。
- `state: unknown` 或 `state_verified: false` 仍需用户在页面核对，不要改用点赞/收藏命令试探。

## 评论

```bash
python "{baseDir}/../../scripts/cli.py" comment-video --video-id <作品ID或公开链接> --comment "评论内容"
```

- 只在页面明确提供评论输入框和发送控件时尝试一次。
- `state: comment_confirmed` 表示评论文本已在评论区出现。
- `state: comment_clicked_unconfirmed` 表示发送控件已点击但未确认评论出现；不要自动重试。
- `comment_input_not_found`、`comment_text_not_applied` 或 `comment_submit_not_found` 表示没有发送评论，不要把填写输入框报告为已评论。
- `comment_input_not_empty` 表示评论框中已有其他草稿；保留草稿且不要覆盖。

## 分享链接

```bash
python "{baseDir}/../../scripts/cli.py" share-video --video-id <作品ID或公开链接>
```

优先返回 JSON 的 `share_url`。`copied_to_clipboard: false` 只表示当前环境没有确认剪贴板写入；只要 `share_url` 有值，仍可把链接交给用户。

## 失败处理

- `risk_page: true`：停在 headed 浏览器，等待人工验证。
- 作品不可访问：说明可能私密、已删除或链接错误。
- 按钮未找到：报告页面结构可能变化，不要用坐标盲点或其他自动化工具兜底。
- 不支持回复评论、私信分享或批量互动。
