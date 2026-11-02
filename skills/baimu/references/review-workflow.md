# 问题单与固定返工清单

读取 `review-context ID` 获取规则，再用 `review-workflow ID` 获取 `workflow_revision`、当前 `report`、`requests` 和 `active_batch`。
使用 `review-action ID --request-file UTF8_JSON` 提交下面三种机器操作。独立试用会话继续在命令前带 `--session-file`。
这些接口保存任务和问题，不自动调用模型或编辑时间线。实际修改仍走已支持的编辑接口。

## 初审

已有 waiting 的请求就读取其 id 和版本；没有时提交：

```json
{"action":"request_review","workflow_revision":"读取值","request_id":"本次唯一请求标识"}
```

任务快照固定 project_revision、rules_revision、scope_revision 和所选规则。新规解释确认后，若 scope_revision 改变，需要重新 request_review 获取当前快照；旧请求会标 superseded。
检查实际成片，计算文件 SHA-256，不用稀疏抽帧或工程检查冒充完整覆盖。结果提交示例：

```json
{
  "action":"submit_report",
  "workflow_revision":"最新读取值",
  "request_id":"waiting 请求的 id，区别于调用方 request_id",
  "artifact":{"path":"实际成片绝对路径.mp4","sha256":"64位小写SHA256"},
  "coverage":"说明实际检查过的画面、声音、区间与未检查部分",
  "findings":[{
    "rule_id":"本次选中规则的 id",
    "start":1.2,"end":2.1,
    "title":"具体问题",
    "certainty":"已确认或待复核等真实程度",
    "evidence":"实际看见/听见的内容，以及对应细则",
    "plan":"准备怎么修及影响范围；证据不足时明确先复核，不盲改"
  }]
}
```

`submit_report` 还应提交 `checks` 数组，每项为 `{rule_id,status,evidence}`。status 使用 pass、issues、needs_review、not_checked；必须给出实际检查说明。pass 不允许同时有对应 findings，issues 需要关联具体问题。未提交结果的项目显示未检查，不能由空问题单推断无问题。旧版报告仍可读，但没有明确通过证据的类别不补造 pass。

每个同规则、同时间段合并为一项，可以同时列出画面、音频、字幕修复。问题默认勾选。审核栏显示各类别检查结果，修改栏显示具体问题和可编辑意见；默认全项检查，已明确自定义的范围继续保留。
同一成片/工程/规则/范围下，重复提交相同位置不会恢复人取消的标注；不要改时间或规则 ID 来绕过人工保留。
返回空 findings 仅表示这次未列出问题，不意味着未覆盖内容也通过。提交失败不直接重试旧 revision。

## 人工选择与返工

审核完成先汇报给人工，等人工选定清单并给出最终意见后执行。人工已说“按清单修改”或点击相应按钮，即按该清单继续，不逐项再问。

人取消标注表示该处保留，不修改全局规则。人可以在任务开始前通过 mark 的可选 plan 字段保存最终修改意见；这份人工意见在同版同处重新报告时保留。人点击「按清单修改」后产生 active_batch，findings 是本轮固定清单，findings[].plan 是固定的最终修改意见。Codex 必须执行这份最终意见，不再读取旧机器建议代替。批次固定后不能直接编辑意见；需取消后重新选择和发起。
用户请求执行该批任务时，按快照中的拟处理方式和当前授权范围执行；按钮授权对应清单内明确的修法，不扩大到无关镜头、外部上传或付费重生成。
不要由机器重新勾选人工保留项，也不要擅自创建批次。新增问题另列，不能加入已经固定的批次。
每次编辑前重读 workflow，确认任务未取消、目标问题仍在本轮、规则版本未变，检查工程 expected_project_revision；遵守轨道锁。
逐项回写（均带最新 workflow_revision）：

```json
{
  "action":"repair_progress",
  "workflow_revision":"最新值",
  "batch_id":"active_batch.id",
  "finding_id":"该批 findings 中的 id",
  "status":"working",
  "project_revision":123,
  "note":"准备对该处执行的局部修改"
}
```

状态顺序：pending → working → awaiting_verification → resolved / unresolved。
- working：修改前工程版本须等于本轮 expected_project_revision。
- 通过编辑接口写入并回读后，报 awaiting_verification，附当前工程 revision 与修改说明；后端更新本轮期望版本。先完成此回写再处理下一处。
- 实际新成片复审后才能报 resolved，同时提供 `verification:{path,sha256,note}`。note 描述实际检查区间、原问题消除及相关回归检查，不凭写入成功编造复审。
- 无法修复、证据不足或受支持能力限制时报 unresolved 和具体原因，继续其它独立项。pending/working 也可转 unresolved。
- cancelled 或 complete 的批次不再接受进度；取消不回滚已经完成的编辑。
- 工程在任务外变化、规则或范围变化时停止相关操作并核对，不用填写当前 revision 掩盖并发变更。

时间线编辑会让原问题单显示旧版本，这是正常的。固定批次以 expected_project_revision 继续跟踪本轮；再次发起修改须重新审核，不能直接套旧问题时间。
