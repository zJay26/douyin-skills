---
name: douyin-publish
description: 在抖音创作者中心填写图文发布表单、上传本地图片、选择音乐、校验页面，并在明确复核后点击发布。用户要求发布抖音图文或检查待发布内容时使用；不用于视频、草稿或定时发布。
---

# 发布抖音图文

只使用 `python "{baseDir}/../../scripts/cli.py" <子命令>` 完成抖音页面操作。可以使用普通图片工具准备和肉眼检查素材，但不要换用其他发布实现。

## 强制流程

严格按以下顺序执行：

1. 确认目标账号并运行 `check-login`。
2. 检查所有图片与文案。
3. 执行 `fill-publish-image`。
4. 执行 `select-music`。
5. 人工查看页面并执行 `validate-publish`。
6. 取得用户发布授权后，执行带 `--confirm` 的 `click-publish`。
7. 根据 `published` 与 `status` 判断是否已确认成功。

不要省略校验，不要在校验读取失败时点击发布。

## 素材要求

- 图片必须是存在的绝对路径，格式为 JPG、JPEG、PNG 或 WebP。
- 优先使用接近 9:16 的竖版成图，避免上下白边、画布留白和异常裁切。
- 标题、正文和至少一张图片都不能为空。
- 发布前逐张检查白条、错字、畸形人脸/手部、局部崩坏、异常 UI 残影、比例和封面裁切。
- 正文先写入 UTF-8 文本文件，并使用绝对路径传给 `--desc-file`。

## 1. 填写表单

```bash
python "{baseDir}/../../scripts/cli.py" fill-publish-image \
  --title "作品标题" \
  --desc-file "/absolute/path/desc.txt" \
  --images "/absolute/path/01.jpg" "/absolute/path/02.jpg"
```

只有 `success: true` 与 `status: filled` 才进入下一步。

## 2. 选择音乐

```bash
python "{baseDir}/../../scripts/cli.py" select-music --names "目标音乐1" "目标音乐2"
```

指定音乐不可用时，CLI 会尝试选择面板中的首个可用音乐。必须看到 `success: true`，并在页面显示“修改音乐”。

## 3. 页面复核与校验

检查标题、正文、图片数量、封面预览和音乐后运行：

```bash
python "{baseDir}/../../scripts/cli.py" validate-publish
```

用户明确要求热点时才加入 `--require-topic`。任何 `errors` 都必须先解决。

## 4. 最终发布

如果用户没有提前授权自动发布，先展示最终标题、正文摘要、图片清单和音乐并询问确认。用户已明确授权时，也必须由执行者完成页面复核。

```bash
python "{baseDir}/../../scripts/cli.py" click-publish --confirm
```

解释结果：

- `published: true`、`status: publish_confirmed`：页面已给出明确成功信号。
- `published: false`、`status: publish_clicked_unconfirmed`：已经点击，但成功状态未知。不要自动重试；先到作品管理核对，避免重复发布。
- `success: false`：未点击或发布前校验失败，按 `validation.errors` 修复。

## 风控与边界

- 优先复用已有的本地 Chrome 调试实例；没有实例时默认 headless，只有 CLI 检测到验证码、身份验证或风控且需要人工处理时才切 headed。
- headed 验证需要用户人工完成，不尝试绕过。
- 不支持视频发布、一键跳过复核、草稿、定时发布、自动素材下载或远程 Chrome 发布承诺。
