---
name: douyin-publish
description: 在抖音创作者中心填写并发布图文或视频作品，包括本地素材上传、视频封面设置、音乐选择、发布前校验和显式确认点击。用户要求发布抖音图文/视频或检查待发布内容时使用；不用于草稿管理或定时发布。
---

# 发布抖音图文或视频

只使用 `python "{baseDir}/../../scripts/cli.py" <子命令>` 完成抖音页面操作。可以使用普通图片、视频工具准备和肉眼检查素材，但不要换用其他发布实现。

## 共同强制流程

1. 确认目标账号并运行 `check-login`。
2. 检查全部素材、标题和文案，并确定本次发布类型是图文还是视频。
3. 使用对应的填表命令，人工查看页面，再使用对应的只读校验命令。
4. 用户没有预先明确授权发布时，展示最终内容并取得授权。
5. 只有校验返回 `success: true`、`state: ready` 后，才执行对应的 `click-publish* --confirm`。
6. 根据 `published` 与 `status` 判断结果；点击后未确认时绝不自动重试。

不要把图文校验器用于视频页，也不要把视频校验器用于图文页。任何 `wrong_page`、验证码/风控、字段不一致、上传未完成或封面缺失都必须先解决。

## 图文发布

图片必须是存在的绝对路径，格式为 JPG、JPEG、PNG 或 WebP。标题、正文和至少一张图片都不能为空；正文先写入 UTF-8 文本文件。

```bash
python "{baseDir}/../../scripts/cli.py" fill-publish-image \
  --title "作品标题" \
  --desc-file "/absolute/path/desc.txt" \
  --images "/absolute/path/01.jpg" "/absolute/path/02.jpg"
```

只有 `success: true`、`status: filled` 且页面中的标题/正文与请求值完全一致时才继续。然后选择音乐：

```bash
python "{baseDir}/../../scripts/cli.py" select-music --names "目标音乐1" "目标音乐2"
```

检查图片数量、裁切、标题、正文和音乐后运行：

```bash
python "{baseDir}/../../scripts/cli.py" validate-publish
```

用户明确要求热点时才加入 `--require-topic`。最终发布命令为：

```bash
python "{baseDir}/../../scripts/cli.py" click-publish --confirm
```

## 视频发布

- 视频必须是存在的绝对路径。支持 AVI、FLV、M4V、MKV、MOV、MP4、MPEG4、MPG、TS、WEBM、WMV。
- 标题和作品简介不能为空；作品简介先写入 UTF-8 文本文件。
- 推荐提供 JPG、JPEG、PNG 或 WebP 自定义封面。发布前必须看到至少一个已设置封面，不能把“AI 封面生成中”当成封面已完成。
- 页面常驻提示里可能出现“上传中”；只有远端视频预览或明确的“重新上传”控件，且没有真实进度条/“上传失败”，才算视频上传完成。

一次上传、填写并设置封面：

```bash
python "{baseDir}/../../scripts/cli.py" fill-publish-video \
  --video "/absolute/path/video.mp4" \
  --cover "/absolute/path/cover.jpg" \
  --title "作品标题" \
  --desc-file "/absolute/path/desc.txt"
```

如果没有在填表时传 `--cover`，命令可能返回 `status: filled_needs_cover`。准备好封面后，在当前视频发布页执行：

```bash
python "{baseDir}/../../scripts/cli.py" set-video-cover \
  --cover "/absolute/path/cover.jpg"
```

人工检查视频预览、标题、作品简介、竖/横封面和可见性设置，再运行：

```bash
python "{baseDir}/../../scripts/cli.py" validate-publish-video
```

用户明确要求热点时才加入 `--require-topic`。任何 `errors` 都必须先解决。最终发布命令为：

```bash
python "{baseDir}/../../scripts/cli.py" click-publish-video --confirm
```

## 结果解释

- `published: true`、`status: publish_confirmed`：页面已给出明确成功信号。
- `published: false`、`status: publish_clicked_unconfirmed`：已经点击，但成功状态未知。不要自动重试；先到作品管理核对，避免重复发布。
- `success: false`：未点击或发布前校验失败，按 `validation.errors` 修复。

## 风控与边界

- 优先复用已有的本地 Chrome 调试实例；只有 JSON 明确返回 `needs_user_verification: true` 才停下请用户处理验证码或身份验证。
- 不尝试绕过验证码、风控或平台限制。
- 不支持一键跳过复核、草稿管理、定时发布、自动远程素材下载或远程 Chrome 发布承诺。
