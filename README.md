# Jev Advisor Community（非官方修改版）

基于 [Jev Windows](https://github.com/jev-chat/jev-chat-windows) 二次开发，集成 [狗头军师](https://github.com/shengjidaguai-china/goutoujunshi) 的部分 MIT 许可参考资料。
本项目不是上述项目、微信、腾讯或模型服务商的官方产品，不代表原作者或相关公司的认可、合作或背书。

## 功能

- Windows 窗口截图与本地 OCR，提取当前聊天窗口文字。
- 只配置一个模型来源和一把 API 密钥，供分析、起草和排序使用。
- 可选军师模式：按当前会话背景给出关系策略和回复候选。
- Ctrl + Alt + J 全局快捷键：开始 / 暂停采集，启动默认暂停。
- 复制或填入输入框；发送始终由用户手动完成。

本次仅发布源码，不提供安装包、模型权重或第三方依赖的二进制副本。

## 运行

Windows 10 1903+ / 11，Python 3.11。先在项目目录执行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe main.py
```

之后可双击 `start-advisor.cmd`。仅看虚构示例可双击 `preview-advisor.cmd`，该预览不采集、不调用 API。
首次启动在设置中选择来源并填写你自己的 API 密钥；模型列表和可用模型以服务商为准。
API 调用可能收费，分阶段分析会发起多次请求。没有附送密钥或额度。

## 数据与使用边界

截图和 OCR 在本机处理，但生成回复时，所选上下文、说话风格及军师背景会发送给你配置的模型服务商；这不是完全离线软件。
API 密钥保存在当前 Windows 用户环境变量 / 注册表中，并非加密保险库。普通设置保存在本地 `config.json`。
会话聊天及军师档案主要保存在进程内存中，军师档案切换会话后失效；本版本没有跨会话长期记忆功能。
软件异常输出、用户自行截屏或导出仍可能包含隐私。不要把密钥、聊天、个人背景或未经同意的截图提交到仓库或 Issue。
仅处理你有权处理的聊天信息，上传模型前应明确相关授权和必要性；遵守适用法律及聊天平台、模型服务商条款。
默认暂停采集，微信窗口需保持可采集状态；回复必须由你核对。不得用于冒充他人、骚扰或未经授权的监控。
AI 可能误读说话人、关系和意图，不保证回复效果，不提供专业心理、医疗或法律服务。

## 修改与署名

修改日期：2026-10-07。相对 Jev Windows 基线 `c6d3a10474ce1ff3b7f8f6402b3b5e0e58fad5f1`：

- 集成当前会话军师策略和分析界面；优化具体关心与自然接话的生成、排序规则。
- 桌面端改为统一模型配置，支持 DeepSeek、Kimi、智谱等已有来源。
- 增加全局采集快捷键，以及会话切换、暂停时的过期结果处理。
- 去掉上游公众号推广入口；修改版不链接上游安装包或检查上游更新。
- 重写发布说明，补充来源、许可、数据流和风险边界。

上游版权属于原作者；本仓库不声称所有代码、资料均为修改者原创。部分开发和说明整理使用 AI 辅助。
详细来源与文件哈希见 [PROVENANCE.md](PROVENANCE.md)，许可证说明见 [NOTICE](NOTICE)。

## 许可

本修改版作为组合程序按 **GNU GPL version 3 only（GPL-3.0-only）** 发布，全文见 [LICENSE](LICENSE)。
其中 Jev 和狗头军师的原始 MIT 许可、版权和上游 NOTICE 保留在 `LICENSES/`；军师资料同时保留自己的 MIT 许可。
此声明不取消原始 MIT 文件的授权，也不把第三方组件或商标变成修改者所有。

你可按适用许可使用、修改和再分发；分发修改版时应保留法律声明、注明修改，并履行 GPLv3 对相应作品的源码等义务。
软件按现状提供，不作担保，责任限制以许可证及适用法律为准。
界面组件 QFluentWidgets 的 README 另有商用授权说明，与标准 GPLv3 允许收费分发的文字存在解释差异；本次为非商业源码分享，不据此承诺你的商业方案已获授权。
闭源、商业发行或捆绑 exe 前，另行确认组件许可及全部二进制依赖、模型、字体和图标的分发义务。

## 检查与限制

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe tools/advisor_demo.py --smoke
```

测试使用虚构或模拟数据，不证明所有聊天版本兼容或 AI 建议可靠。
[发布检查报告](docs/RELEASE-REVIEW.md) 是有限范围的工程检查，不是法律意见或零侵权保证。
依赖元数据清单见 [DEPENDENCIES.md](DEPENDENCIES.md)。本次未发布上游旧截图、公众号二维码、图标和 Git 历史。
