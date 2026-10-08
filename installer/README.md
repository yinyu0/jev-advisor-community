# Jev Advisor Community 0.2.0 联网安装版

适用于 Windows 10 1903+ / Windows 11 x64。建议预留 3 GB 空间。

双击 `JevAdvisorCommunity-0.2.0-online-setup.exe`，按提示安装。
也可将 ZIP 完整解压后双击 `setup.cmd`。无需管理员权限。
安装需要访问 GitHub 和 PyPI，网络受限时可能失败；安装窗口会显示原因。
本包没有代码签名，Windows 可能显示未知发布者。仅从可信来源获取并核对 SHA256SUMS.txt；不要关闭系统安全防护。

默认目录：`%LOCALAPPDATA%\Programs\JevAdvisorCommunity`。
安装成功后使用桌面快捷方式或目录内 `Launch.cmd` 启动。
设置里填写自己的模型 API 密钥，采集默认暂停。API 使用可能收费。
卸载：先退出软件，再运行安装目录内 `Uninstall.cmd`，输入 REMOVE 确认。
卸载会删除该目录的设置，但保留 Windows 用户环境变量里的共享模型密钥。
不会覆盖已有安装。失败留下的目录确认不含所需数据后可自行删除，再重新安装。

这是联网引导安装包，不是离线完整包。包内包含完整修改版源码、安装脚本、GPLv3 和原始 MIT 声明，不含 API 密钥、个人聊天、第三方 wheel 或 OCR 模型副本。
安装时下载固定版本 Astral uv（校验 SHA256），由 uv 下载 CPython 3.11.17，并从 PyPI 安装 requirements-lock.txt 中固定版本的依赖。安装器使用 installer/requirements-hashed.txt 强制核对下载包的 SHA256。
Python 运行时来自 Astral python-build-standalone，并非 python.org 的官方 Windows 安装程序；包索引依赖下载和完整性处理交由 uv。
第三方组件各自许可仍适用，安装到本地不等于允许任意重新分发整个安装目录。
本项目没有声称完成所有第三方 wheel 内部模型或素材的授权审计。

源码和上游署名见包内 source.zip，以及 https://github.com/yinyu0/jev-advisor-community 。
GPL-3.0-only；非官方修改版，无原作者、微信或模型服务商背书。
截图和 OCR 在本机处理，选定上下文会发给用户配置的模型服务商。

开发者构建：在源码 Git 工作区运行 `python installer/build.py <输出目录>`，需要 Windows 自带 IExpress。
测试安装可执行 `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -InstallDir <空目录> -NoShortcuts`。
