# 百慕 Baimu

面向 AI Agent 的本地视频剪辑软件，也支持可视化编辑。

[下载最新稳定版](https://github.com/kuro19711/baimu/releases/latest)

## 功能

- 导入素材，按剧目和分集管理工程。
- 在多轨时间线上移动、裁剪、切分片段，调整音轨、字幕和打码。
- 按音频对齐 TXT 对白，或通过本地语音识别制作字幕。
- 预览、保存历史版本、批量导出视频。
- 在支持的范围内交接剪映工程，继续精修。

## 安装

在 Releases 下载 `baimu-windows-x64.zip`，完整解压，按包内安装说明操作。适用于 Windows x64，包含运行环境及语音识别模型。

使用 Agent 时，可按需要下载配套的 `baimu-agent-skill.zip`。使用 Codex 时，将其中的 `baimu` 文件夹放入用户的 `.codex/skills` 目录，重新打开会话。

源码见 `baimu-source.zip`，下载校验值见 `SHA256SUMS.txt`。第三方组件许可随软件保留，清单见 `THIRD-PARTY-LICENSES.txt`。

## 更新与反馈

后续稳定版继续通过本仓库发布，最新版下载链接保持不变。问题反馈请提交 [Issue](https://github.com/kuro19711/baimu/issues)。

部分剪映效果、字体和模糊表现存在兼容限制，交付前请检查画面与声音。
