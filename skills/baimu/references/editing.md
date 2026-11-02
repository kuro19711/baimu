# 编辑、素材和历史恢复

适用于有对应接口的百慕安装。先用 `status` 看实际后台版本与安装构建，按当前安装的
`web/timeline-model.js` 和 `AI接口说明.txt` 选字段；接口不支持时报告差异，不直接改工程文件。

## 联动、选区与不同长度的视频替换

编辑视图时间单位是秒，音量是 dB；原生 timerange 使用微秒，volume 使用线性值。
`revision` 可能是非单调指纹，每次写入后采用服务返回的新值。

已分离的 dialogue 仍可能通过 `native_links` 与画面分组。移动、裁剪、切分、删除任一侧会联动；
单改声音需先提交 `{"type":"unlink","kind":"dialogue","id":"原声ID"}`，再用新 revision 编辑。
不要同时恢复画面内嵌声音和已关联原声，避免双重播放。

将以下对象放入 `apply-edits --operations-file` 的操作数组：

```json
[
  {"type":"move_selection","items":[{"kind":"video","id":"画面ID"},{"kind":"caption","id":"字幕ID"}],"delta":1}
]
```

整组按帧平移，保留相对位置，关联原声只跟随一次；未选轨道不动。
`reorder_selection` 采用 `id`（拖动的画面）、`items` 和 `targetIndex`，只接受连续镜头块插入排序。
普通视频 trim/update/remove 可传 `magnetic:false` 保留后续画面绝对位置。
“主轨磁吸”控制合拢，“自动吸附”控制拖动对齐，“联动设置”控制是否连选独立轨道，三者不同。
当前多选不支持批量裁剪或删除，不把一次移动推断为用户同意改变其他独立轨道。

替换单个镜头，先把新视频导入当前工程素材列表，再构造：

```json
[
  {"type":"replace_video","id":"画面ID","asset_id":"新素材ID","in":0,"out":3,"strategy":"fit","follow":[]}
]
```

| strategy | 时间线行为 |
| --- | --- |
| `fit` | 保持原镜头长度并裁切；新选段不足则拒绝 |
| `gap` | 后续画面起点不动；长则裁切、短则留空 |
| `ripple` | 采用新选段长度并推动后续画面 |

`follow` 仅用于 ripple，可选 `caption`、`narration`、`bgm`、`sfx`、`mask`、`dialogue`。
只推动起点在原镜头结束之后的指定类型，跨边界的长声音不自动截断。
确认来自旧画面的联动原声会一起换源，独立声音及同素材的其他镜头不换。
多音轨须提供 `audio_stream`；新视频无声且旧原声仍联动时会拒绝，需先核对是否解除联动。

## 素材移动、同路径更新与替换的区别

文件内容相同、只是位置改变：

```text
baimu_client.py media-status PROJECT_ID
baimu_client.py relink-preview PROJECT_ID --revision REVISION --asset-id ASSET_ID --path C:\素材\新位置.mp4
baimu_client.py relink-asset PROJECT_ID --revision REVISION --asset-id ASSET_ID --path C:\素材\新位置.mp4 --expected-sha256 预检返回的SHA256 --confirmed
```

预检必须返回 `identical:true`。沿用同一 revision、路径和预检的 `asset.sha256`；若期间工程或文件改变，
重新核对，不能原样强行重试。保留素材ID、所有引用的裁切、位置、声音联动和未知字段。
旧素材缺校验值或内容不同，不能按同名、时长接近自动认定相同。
`--confirmed` 表示用户已授权这次重连，不要求在已有授权后再重复询问。

原路径上的文件内容已被用户替换时：

```text
baimu_client.py refresh-assets PROJECT_ID --revision REVISION --asset-ids ASSET_ID --confirmed
```

会影响该素材的所有引用及可确认来源的关联原声；用户独立换过的声音不覆盖。
它不接收新路径；只换一个镜头请用 `replace_video`。

## 字幕参数、模板和视觉边界

通过 `fonts` 获取字体及 `jianying_font_size` 标定记录。不要把界面面板数字直接写进编辑视图：

| 编辑视图字段 | 含义／转换 |
| --- | --- |
| `font_size` | 1080参考画布的内部像素；剪映字号 = 内部值 × 字体标定比率 |
| `x`、`y` | 左上原点的0～100百分比；原生位置分别为 `(x-50)/50`、`(50-y)/50` |
| `outline` | 内部像素；当前剪映面板兼容值为内部值 ×5 |
| `opacity`、`outline_opacity`、`shadow_opacity` | 0～1 |

字体标定须匹配画布比例；无匹配记录时采用1/8兼容系数，不能称为视觉标定。
内置已标定 Noto Sans SemiBold 在9:16下，内部64对应剪映14。
界面剪映位置：`X=(x-50)×画布宽/50`、`Y=(50-y)×画布高/50`。
例如1080×1920面板Y=-800对应 `y=70.8333333333`。
只改字体时内部像素字号不变；要保持剪映面板字号须用新字体比率同时换算 `font_size`。

复用已确认样式时，将编辑视图的样式字段用 `type:style,kind:caption,scope:all,patch:{...}` 应用；
这会清除被修改字段的逐条覆盖。只改一条用 `scope:one,id:字幕ID`，不意外改整集。
参考图片用于制定参数和预览对照，不能声称有图片自动标定接口；行数和标点按用户要求处理，不设全局两行限制。

字幕额外片段缩放、动画、多样式文字及复杂原生效果会保留并可能阻止不完整本地合成。
字体、换行、描边、阴影、模糊与剪映的最终效果仍需实际画面验收，不能仅凭参数回读宣称一致。

## 历史恢复与工程管理

```text
baimu_client.py history PROJECT_ID
baimu_client.py get-project PROJECT_ID
baimu_client.py restore PROJECT_ID --revision 当前REVISION --history-revision 目标历史REVISION
```

`history` 返回最近100份快照，按保存时间从新到旧；revision 数值更大不代表更新。
历史排序和恢复保护以构建 `060shared3u20261024140940` 为已验证基线；较早同号包可能缺少这些修复。
先核对实际运行构建是否包含修复，不能仅因新 skill 提供 restore 命令就向旧后台执行整集恢复。
恢复是整集历史操作，须与用户要求的目标和范围一致；局部改错优先局部修正，不自动恢复整集。
恢复使用当前 revision，并回读新版本；遵守字幕、画面、声音等轨道锁，不用恢复绕过回收站流程。
不要删除历史或复制历史 JSON 覆盖工程。无效目标、锁或冲突时保留现状并报告。

`library` 返回剧目和分集信息；界面支持名称和修改时间排序，排序选择存储在浏览器本地，
不是工程时间线字段，没有为此修改工程或批量写回的 API。

## 剪映命名、任务与结果核对

安全交接时使用“剧名＋集数”，例如 `三个硬币7`；同名去重为 `三个硬币（2）7`。
旧百慕自有ID目录在可安全交接时原地迁移，剪映占用时延后；不迁移外部草稿目录。
交接后回剪映首页重新打开。目录、索引一致不等于剪映 GUI 保存重开验收完成。

导出后检查 job 的真实完成状态及 `result.output`（后台成片路径）；下载另存位置另行核对。
任务快照不会随排队后编辑自动更新。修改声音或镜头后，重新核对字幕同步与受影响切点。
新版预览合并到下一动画帧刷新；接口成功后先核对当前 revision 和实际画面，避免重复提交同一次操作。
