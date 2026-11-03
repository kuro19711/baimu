# 百慕本机 API 速查

## GitHub 更新检查

`status` 的 `updates` 与 `check-updates` 共用随技能安装的 `scripts/baimu_updates.py`，旧版软件也能检查。`check-updates --force` 用于人工立即重查。

实际请求 GitHub 的 `https://github.com/kuro19711/baimu/releases/latest`，跟随公开重定向取得正式发布标签；不把源码提交当作软件更新。更新模块不使用本机会话令牌，也不上传工程信息。

缓存位于 `%LOCALAPPDATA%\Baimu\updates\state.json`，按电脑本地自然日记录尝试日期、成功结果和已提醒版本。OS 文件锁覆盖“检查日期→联网→写入”，保证多个对话/进程自动检查去重；检查失败或中断也占用当天自动尝试，人工可用 `--force` 重试。`cached=true` 表示复用记录；`status=error/interrupted/unavailable` 不能说已确认最新版。仅 `notify=true` 时主动提醒，用户主动查询时仍可展示缓存结果。

集成更新模块的软件提供 `GET /api/updates` 和 `POST /api/updates/check`，后者接受布尔值 `force`、`claim_notice`。软件与技能使用同一用户级缓存；这些接口需要本机鉴权，不执行安装或重启。旧版无此接口时继续使用随技能脚本。

## 内置审核 skill 与本集选择

- `review-skills`：GET `/api/review-skills`，返回 `review`、`repair` Markdown、`revision` 和解析的 `sections`。
- `review-context ID`：GET `/api/projects/{id}/review-context`，返回两份原文、`selected_review_markdown`、
  `selected_ids`、`sections`、`common`、`needs_clarification`、`rules_revision`、`scope_revision`、`project_revision`。
- POST `/api/review-skills`：`{revision,review,repair}`，原子保存两份文档，版本冲突拒绝；保留旧文档快照。
- POST `/api/projects/{id}/review-scope`：`{rules_revision,scope_revision,selected_ids}`。空数组表示本次未选检查项。
- `confirm-review-rule ID --rules-revision R --scope-revision S --rule-id RULE --interpretation-file FILE --confirmed-by-user`：
  POST `/api/projects/{id}/review-confirmation`，正文为 `{rules_revision,scope_revision,id,interpretation,confirmed_by_user:true}`。
  仅记录用户已确认的解释，各集共用，不是审核通过或返工授权。

这些数据单独保存在百慕数据目录的 review 下，不进入剪映时间线；Agent 仍仅通过接口访问。
二级 ATX 标题生成检查项，正文修改保留选择，改名视为新项；代码围栏内标题不参与。
新增项默认选中并待确认理解，取消勾选不会删除规则；默认规则的既有含义无需重复确认。
全局通用说明或返工文档变更也会出现在待确认列表，不能只核对小标题。

本 Skill 的脚本只暴露经过约束的常用操作。百慕软件仍然是数据和业务规则的唯一权威。

## 发现与鉴权

- 安装记录：`%LOCALAPPDATA%\Baimu\installation.json`
- 会话记录：安装记录 `data` 目录下的 `session.json`
- 服务必须是 `http://127.0.0.1:<port>`。
- 临时令牌位于会话 URL 的 fragment 中，请求使用 `X-Studio-Token`。
- 令牌不得写入请求文件、聊天、源代码、持久日志或外部服务。

## 读取命令

| 客户端命令 | 百慕接口 | 用途 |
| --- | --- | --- |
| `status` | `/api/identity`、`/api/health`，本机安装记录 | 分别报告后台版本、安装路径和包内构建号及任务状态 |
| `projects` | `/api/bootstrap` | 列出工程及当前版本 |
| `library` | `GET /api/library` | 剧目文件夹和分集信息 |
| `fonts` | `GET /api/bootstrap` 的 `fonts` | 字体、字号换算和标定画布 |
| `get-project ID` | `/api/projects/{id}` | 读取可编辑工程和 `revision` |
| `native-timeline ID` | `/api/projects/{id}/native-timeline` | 读取原生轨道和素材结构 |
| `editor-state ID` | `/api/projects/{id}/editor-state` | 检查轨道锁和原生编辑器状态 |
| `quality ID` | `/api/projects/{id}/quality` | 读取自动质量检查 |
| `job ID` | `/api/jobs/{id}` | 查询导出任务真实状态 |
| `history ID` | `GET /api/projects/{id}/history` | 按保存时间列出最近100份历史 |
| `media-status ID` | `POST /api/projects/{id}/media-status`，`{}` | 读取素材是否丢失；该 POST 不修改工程 |

同一 `version` 可对应不同 `build_id`。`status.identity` 是后台实际报告，`status.installation` 是磁盘安装记录和安装目录的 bundle，
二者分别核对，不把磁盘信息当成已运行新构建的证明。功能仍以实际接口支持为准。

## 编辑请求

`apply-edits` 的 JSON 文件可以是操作数组，也可以是包含 `operations` 的对象：

```json
[
  {"type": "move", "kind": "video", "id": "片段ID", "targetTime": 4},
  {"type": "update", "kind": "caption", "id": "字幕ID", "patch": {"text": "新字幕"}}
]
```

支持的操作和字段以当前安装版本的 `web/timeline-model.js` 为准。时间线操作使用秒；原生补丁可能使用微秒，
不要混用。所有操作由百慕原子提交，任一操作失败时整批不应写回。
多选、画音联动、视频替换、字幕单位与样式复用见 [editing.md](editing.md)。

## 素材重连、刷新和历史恢复

| 命令 | POST 请求体 |
| --- | --- |
| `relink-preview ID --revision R --asset-id A --path FILE` | `/api/projects/{id}/relink-preview`：`revision,asset_id,path` |
| `relink-asset ID --revision R --asset-id A --path FILE --expected-sha256 HASH --confirmed` | `/api/projects/{id}/relink-asset`：上述字段及 `expected_sha256,confirmed:true` |
| `refresh-assets ID --revision R --asset-ids A B --confirmed` | `/api/projects/{id}/refresh-assets`：`revision,asset_ids,confirmed:true` |
| `restore ID --revision R --history-revision H` | `/api/projects/{id}/restore`：`revision,history_revision` |

所有写入前检查当前版本，成功后回读核对服务返回版本；锁、冲突、文件变化等错误不强制重试。
重连预检必须确认相同内容，传回预检的 SHA-256；原路径内容改变才用 refresh-assets。
历史恢复作用于整集，不用来绕过回收站或轨道锁；revision 不代表时间顺序。
适用场景、影响范围和完整示例见 [editing.md](editing.md)。

## 自动做字幕（TXT 对齐或直接识别）

百慕需要已配置本地 faster-whisper 模型。以下命令不接管页面，不自动联网下载模型：

```text
baimu_client.py align-subtitles PROJECT_ID --revision REVISION --text-file C:\素材\对白.txt --language zh --split lines
baimu_client.py transcribe PROJECT_ID --revision REVISION --language zh
baimu_client.py job JOB_ID
baimu_client.py get-project PROJECT_ID
baimu_client.py apply-subtitles PROJECT_ID --revision 最新REVISION --job-id JOB_ID --replace-existing
```

`--split lines` 每个非空行一条，`sentences` 按句末标点分句。TXT 最多 1 MiB、20000 个对白字符，
支持 UTF-8、带 BOM 的 UTF-16 和 GB18030。粘贴原文可原样保存成临时 UTF-8 TXT 后使用同一入口。
`--language` 是音频语言；省略时自动检测，不继承工程可能过时的默认葡萄牙语。
原文应为本集原语言对白，不带角色标签或动作说明；不改成翻译或识别转写文字。

提交走 `POST /api/projects/{id}/jobs`：

```json
{
  "kind": "transcribe",
  "revision": 12345,
  "language": "zh",
  "subtitle_text": "第一句对白。\n第二句对白。",
  "subtitle_split": "lines"
}
```

不带 `subtitle_text` 时直接识别最终音轨生成字幕。TXT 对齐采用最终混音的 ASR 逐词时间匹配输入原文；
词内边界为估计，不保证字级精度。任一句文字匹配率不足 65% 时任务失败，不替换现有字幕。

`GET /api/jobs/{job_id}` 完成后返回 `result.captions`、`result.sound_digest`，TXT 任务另有
`result.alignment`（总体和逐句文字匹配率）及 `view_reference`（提交时的编辑视图）。
文字匹配率不等于时间精度或人工试听结论。

`apply-subtitles` 检查任务归属、完成状态、当前声音指纹、字幕轨道锁及提交后字幕是否改变。
用当前版本执行差量 `POST /api/projects/{id}`，只提交 `revision` 与 `captions`，原子替换本集字幕，
保留其余工程字段、原生未知字段和历史；可应用超过100条字幕，不要分批先删后加。
`--replace-existing` 仅在用户已授权替换已有字幕时使用，不是对任意工程的通用覆盖许可。
写入后回读核对，不强制重试并发冲突，也不自动执行剪映交接或导出。

## 剪映交接

```text
baimu_client.py handoff PROJECT_ID --revision REVISION --confirm-jianying-closed
```

`--confirm-jianying-closed` 表示已经确认用户保存并离开了目标草稿；它不是对未知目标的通用授权。
名称、目录和索引按“剧名＋集数”同步；旧百慕自有ID目录在可安全交接时迁移，外部草稿不移动。
剪映占用时可能延后迁移。交接后从剪映首页重新打开；接口成功不代表 GUI 保存重开验收。

## 批量导出

请求文件示例：

```json
{
  "request_id": "32位十六进制唯一ID",
  "kind": "draft",
  "projects": [{"id": "工程ID", "revision": 12345}],
  "options": {"enhance_hd": false}
}
```

一次提交 1 至 100 集。相同重试必须保留相同 `request_id` 和相同内容。
每个任务捕获提交时快照，之后编辑不改变已排队内容。完成后的 `result.output` 是后台实际生成路径；
下载另存位置须另外核对。复杂原生效果可能需要剪映合成，不能忽略效果后输出。
