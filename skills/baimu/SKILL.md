---
name: baimu
description: 通过九州百慕本机接口读取、检查和修改真实剪辑工程。用户提到百慕、百慕工程，或要求在百慕中剪辑、导出、交接剪映、按 TXT/粘贴对白对齐字幕或按音频自动做字幕时使用；不用于脱离百慕工程的通用创作建议或单纯生成媒体。
metadata:
  version: "2026.11.03.2"
---

# 九州百慕

把百慕桌面软件视为工程和时间线的唯一权威。通过本 Skill 随附的
`scripts/baimu_client.py` 调用百慕本机 HTTP API；不要直接修改百慕数据目录、工程 JSON、
历史记录或剪映草稿。

## 连接

接入时运行 `status`，其中的 `updates` 会检查 GitHub 最新正式发布。软件尚未启动时用 `check-updates`。检查脚本按电脑本地自然日共享缓存和进程锁，不同对话、工程和软件窗口当天只自动联网检查一次；失败也记录当天尝试。仅当 `notify=true` 时主动提醒并附 `latest.release_url`，其它情况继续任务，不再另开网页重复检查。用户要求立即检查时运行 `check-updates --force`；检查不会自动安装或重启软件。

1. 首先运行客户端的 `status`，读取后台实际版本、安装记录和包内构建号。同一软件版本可能有多个构建；安装记录不能证明当前后台已切换，也不能证明每个功能都已验收。
2. 客户端从 `%LOCALAPPDATA%\Baimu\installation.json` 找到数据目录（兼容旧版安装记录），再读取
   `session.json` 中的本机地址和临时令牌。不要在聊天、日志、仓库或命令行参数中输出令牌。
3. 如果连接失败，请用户启动百慕桌面软件；不要猜测端口、令牌或工程路径。

运行脚本时使用当前环境中可用的 Python 3。若普通 `python` 不可用，使用 Codex 工作区随附的
Python。先解析本 Skill 目录的绝对路径，不要复制或临时重写客户端实现。

常用命令：

```text
baimu_client.py status
baimu_client.py check-updates
baimu_client.py check-updates --force
baimu_client.py projects
baimu_client.py get-project PROJECT_ID
baimu_client.py native-timeline PROJECT_ID
baimu_client.py editor-state PROJECT_ID
baimu_client.py library
baimu_client.py fonts
baimu_client.py history PROJECT_ID
baimu_client.py media-status PROJECT_ID
baimu_client.py apply-edits PROJECT_ID --revision REVISION --operations-file FILE.json
baimu_client.py handoff PROJECT_ID --revision REVISION --confirm-jianying-closed
baimu_client.py batch-export --request-file FILE.json
baimu_client.py job JOB_ID
baimu_client.py align-subtitles PROJECT_ID --revision REVISION --text-file 对白.txt --language zh
baimu_client.py transcribe PROJECT_ID --revision REVISION --language zh
baimu_client.py apply-subtitles PROJECT_ID --revision REVISION --job-id JOB_ID
```

接口与命令详见 [references/api.md](references/api.md)。多选联动、替换、重连、字幕参数及历史恢复时读取
[references/editing.md](references/editing.md)。构造时间线操作前，还应读取当前安装目录的 `web/timeline-model.js`；
开发源码可能领先于运行版本，不要依据候选源码向旧后台发送尚未支持的字段。

## 读取与分析

- 用 `projects` 确认剧目和分集，不根据相似名称自行选择有歧义的工程。
- 用 `get-project` 读取工程及当前 `revision`；需要原生剪映时间线时再用 `native-timeline`。
- 用户只要求检查、分析或方案时，只读，不修改工程。
- 区分接口数据验证与真实画面、声音验收。

## 制作前准备

剪辑前读取 [references/production.md](references/production.md)，核对分镜、纯净稿、录音与视频的对应关系，再按用户要求完成制作。

## 从百慕读取审核与返工规则

审核栏显示各项目检查状态，修改栏列出可编辑的最终修改意见。先审核汇报，人工选定清单后再返修。执行机审或固定返工任务时，先读 [references/review-workflow.md](references/review-workflow.md)：
用 `review-workflow PROJECT_ID` 领取初审请求或固定清单，用 `review-action PROJECT_ID --request-file FILE.json`
提交真实问题及返工进度。检查范围勾选与问题修改标注不同；不得恢复人工取消的标注或扩大已经固定的批次。

用户要求在百慕审片、检查审核问题或审后返工时，确定工程后首先运行
`baimu_client.py review-context PROJECT_ID`。从百慕读取当前两份内置 skill、本集勾选范围、
规则版本和已确认解释；不要用记忆或外部审片 skill 中的旧规则覆盖软件里人工修改的新要求。
查看全局原文用 `review-skills`。规则位于主页「审核与返工规则」，本集范围位于草稿「审核」页。

用户明确选择独立试用版时，可使用 `baimu_client.py --session-file 试用数据目录/session.json review-context PROJECT_ID`。
该参数必须在命令前，仍只连接记录中的 127.0.0.1 服务。不修改默认安装发现记录，也不把试用配置当作正式工程配置。

- 按 `selected_review_markdown` 与 `selected_ids` 检查，读取 `repair_skill` 决定返工方法。
  `review_skill` 是完整原文供追溯，不意味着未勾选项也要检查。全部未勾选时报告未选择范围，不暗中改成全选。
- 检查 `needs_clarification`：对照新增规则、旧解释和用户本次要求。
  用户本次原话已明确的要求直接采用；只对影响结果的歧义集中询问，继续其它明确工作。
- 用户确认后，把准确解释保存为 UTF-8 文本，用
  `confirm-review-rule PROJECT_ID --rules-revision R --scope-revision S --rule-id ID --interpretation-file FILE --confirmed-by-user`
  写回。保存后重新读取 context；原文再次变更会重新待确认。
- 记录 `rules_revision`、`scope_revision` 与工程/成片版本。执行返工前重新读取，规则或范围变化时重新核对相关结论。
  勾选、解释确认、规则文字本身都不是修改工程或外部上传授权，仍以当前用户任务范围为准。
- 接口不可用时说明运行版本尚不支持，不能声称已读取内置要求，也不能悄悄回退到旧标准继续审片。
  这是读取规则和协作入口；不代表百慕已内置自动看片模型或已经审核。

## 修改

1. 修改前重新读取目标工程，使用刚取得的 `revision`。
2. 一次提交 1 至 100 条支持的编辑操作。服从轨道锁，不绕过并发检查。
3. 遇到版本冲突时重新读取并重新计算；不要强制覆盖，也不要原样自动重试旧操作。
4. 修改后再次读取工程，核对新版本和目标字段。
5. 保留未知字段、原素材、原生复杂效果和现有实验数据；局部修复不得重建整份草稿。

## 新增编辑与恢复能力

- 修改画面会联动已分组原声；分轨不等于解除联动。只改原声时先明确解除，再编辑对应音频。
- 多选整组移动和不同长度的视频替换，先确定哪些独立字幕、旁白、音乐需要跟随；未选轨道保持原位置。
- 素材移动走“状态检查→重连预检→按校验值重连”；文件内容改变走同路径刷新或单镜头替换，不能混用。
- 历史列表按保存时间排列，原生 revision 是指纹整数，不按数值大小判断先后。只在用户要求恢复指定历史时执行 restore；操作失败不自动回滚整集，也不覆盖轨道锁或改变回收站状态。
- 历史排序及恢复保护依赖软件更新，已在构建 `060shared3u20261024140940` 验证。若仍运行较早的同号构建，未确认包含修复前不执行整集恢复；更新 skill 不能替代更新软件。
- 编辑请求成功后回读服务状态。新版预览在下一绘制帧刷新；数据成功不代表当前页面已完成绘制，不因短暂旧画面重复提交写入。

## 自动做字幕 / TXT 对齐

用户说“给第X集做字幕”“把这份 TXT 对齐成字幕”“按音频分配字幕”时，执行字幕流程，
不要只返回字幕文案或让用户到页面点按钮。目标集和对白明确、且用户已要求写入时，
在任务完成并检查通过后继续写入，不把预览作为必须再确认的一步；用户要求先预览时只生成草稿。

- 先确定工程和 TXT 路径。粘贴对白可原样保存成临时 UTF-8 TXT；有多个同名集或候选文件时先消除歧义。
- 有 TXT 用 `align-subtitles`；没有提供原文、只要求按声音做字幕时用 `transcribe`。
  语言指音频所说语言，已知则指定 `--language`，未知留空自动检测，不擅自翻译。
- 查询 `job` 直到 `complete`，检查 `result.captions`、`result.alignment`（TXT 任务）和错误信息。
  排队不代表字幕已完成；匹配不足、无声或缺模型时保留当前字幕并报告原因，不用均分时长假装对齐。
- 重新读取工程及 revision，使用 `apply-subtitles` 写入并回读。已有字幕且用户已授权替换时传
  `--replace-existing`；未授权则先说明实际替换范围。任务期间字幕或声音改变时停止覆盖并重新核对。
- 结果包含条数、工程版本、低匹配/需试听位置。写入不等于人工试听完成，也不自动导出或交接剪映。

命令参数和请求字段见 [references/api.md](references/api.md)。不要直接改工程文件。

## 剪映交接与导出

- 交接前确认用户已经保存并离开剪映中的目标草稿，重要工程建议退出剪映。
- 使用当前工程版本执行 `handoff`。完成后提醒用户从剪映首页重新打开草稿。
- 批量导出重试必须保持相同 `request_id` 和相同请求内容；只重试失败项。
- 导出提交后用 `job` 查询真实状态，不能把入队成功表述为成片完成。
- 草稿名称采用“剧名＋集数”，同名去重仍保留集数在最后。旧 ID 目录在下一次安全交接时迁移；不直接移动外部剪映草稿，也不因安装新版本就认为全部旧草稿已改名。
- 已完成导出的 `result.output` 是后台实际生成路径；用户下载另存的路径是另一份文件，分别报告。

## 交付说明

报告修改内容、未修改内容、当前工程版本、是否已导出或交接，并明确哪些结果经过自动验证，
哪些仍需要用户在百慕或剪映中看片、试听、保存和重开确认。
原生字幕额外缩放、动画、多样式文字及复杂效果可能需要剪映合成；参数可逆、未知字段保留均不代表画面完全一致。
不把安装包包含修复、自动测试通过或一次字幕任务完成表述为“所有历史反馈已解决”。
