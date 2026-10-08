# 来源与修改记录

这是全新源码快照，未复制上游 Git 历史；保留原始作者、许可证和 NOTICE，不宣称独立原创。

## Jev Windows

- 来源：https://github.com/jev-chat/jev-chat-windows
- 基线提交：c6d3a10474ce1ff3b7f8f6402b3b5e0e58fad5f1
- MIT 版权及许可：LICENSES/Jev-MIT.txt；原 NOTICE：LICENSES/Jev-NOTICE.original.txt

| 发布文件 | 相对该基线 |
| --- | --- |
| `app/__init__.py` | 原样沿用（MIT） |
| `app/advisor_dialog.py` | 新增（本修改版） |
| `app/advisor_state.py` | 新增（本修改版） |
| `app/capture.py` | 原样沿用（MIT） |
| `app/capture_hotkey.py` | 新增（本修改版） |
| `app/chatapps.py` | 原样沿用（MIT） |
| `app/debugwin.py` | 原样沿用（MIT） |
| `app/fill.py` | 原样沿用（MIT） |
| `app/i18n.py` | 原样沿用（MIT） |
| `app/ocr.py` | 原样沿用（MIT） |
| `app/ocr_windows.py` | 原样沿用（MIT） |
| `app/overlay.py` | 修改（原 MIT 部分保留） |
| `app/settings.py` | 修改（原 MIT 部分保留） |
| `app/update.py` | 修改（原 MIT 部分保留） |
| `app/version.py` | 原样沿用（MIT） |
| `app/worker.py` | 原样沿用（MIT） |
| `core/__init__.py` | 原样沿用（MIT） |
| `core/advisor.py` | 新增（本修改版） |
| `core/draft.py` | 修改（原 MIT 部分保留） |
| `core/engine.py` | 修改（原 MIT 部分保留） |
| `core/jev_client.py` | 修改（原 MIT 部分保留） |
| `core/llm.py` | 修改（原 MIT 部分保留） |
| `core/llm_judge.py` | 新增（本修改版） |
| `core/providers.py` | 修改（原 MIT 部分保留） |
| `core/questions.py` | 修改（原 MIT 部分保留） |
| `main.py` | 修改（原 MIT 部分保留） |
| `tests/test_advisor.py` | 新增（本修改版） |
| `tests/test_capture_hotkey.py` | 新增（本修改版） |
| `tests/test_llm_judge.py` | 新增（本修改版） |
| `tests/test_provider_settings.py` | 新增（本修改版） |
| `tests/test_runtime.py` | 新增（本修改版） |
| `tests/test_single_model.py` | 新增（本修改版） |
| `tools/advisor_demo.py` | 新增（本修改版） |

## 狗头军师资料

来源：https://github.com/shengjidaguai-china/goutoujunshi；原版权 powerycy，MIT。
以下与本机安装的原 Skill 对应文件逐字核对一致（忽略 CRLF/LF）。未复制私人档案。
来源提交号未记录，不伪称来自当前最新版本；以本表 SHA-256 固定发布内容。

| 发布文件 | 来源路径 | SHA-256 |
| --- | --- | --- |
| `resources/advisor/core.md` | `SKILL.md` | `825edd66bed33ce514c12d0cd3f2f002417c7aa357b58a6aae658cad26f6e083` |
| `resources/advisor/reply.md` | `references/practical/实战话术编排器：从一句回复到后续分支.md` | `83014b57788a4d6cfe4cb82fe224d81ee5e9ac6d6e84f7ac67097d06828cb7fe` |
| `resources/advisor/invite.md` | `references/practical/主动表达、第一次见面与自然接触.md` | `bd52dec6e84d0e986b5c56edd1320e23254d48d00be5dc249a555063d071abff` |
| `resources/advisor/withdraw.md` | `references/practical/关系投入失衡：互惠判断、降级投入与退出决策.md` | `4e724e9a5b272ad1a6833ddbb9d84eeb86c3b2e395e5f241d90f8655930c77c3` |

这些是摘选参考资料；其中指向完整 Skill 其他章节的相对路径仅记录来源，不表示本程序打包了那些章节或实现了长期记忆。

## 未发布内容

个人 config.json、.env、API 密钥、.venv、日志、聊天导出、真实截图、旧上游截图和二维码、图标、模型权重、旧 exe、自动二进制发布工作流、原 Git 历史均未复制。
文档里的第三方姓名、项目名及论文链接用于出处或说明；本仓库不包含童锦程本人照片、声音、视频或其独立 Skill，也不声称获得其背书。

## 0.1.0 联网安装器

2026-10-07 新增 installer/ 下的构建、安装、卸载脚本和说明，按本项目 GPL-3.0-only 发布。
EXE 由 Windows IExpress 生成，承载同一份完整源码 ZIP、安装脚本与许可文本。没有复制已有个人运行环境。
安装时另外下载 Astral uv 0.12.23（固定 SHA256）、其管理的 CPython 3.11.17 及固定版本的 PyPI 依赖；这些第三方二进制不嵌入发布包。

## 0.2.0 修改（2026-10-08）

新增通用窗口截图助手、DPAPI 档案存储、手动编辑与生成流程，以及对应测试和说明。保留原微信采集路径、版权及非官方声明；未携带真实截图、聊天或用户档案。联网安装器源码随仓库提供，本次没有发布新的二进制安装包。
