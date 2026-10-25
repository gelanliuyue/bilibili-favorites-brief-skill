# bilibili-favorites-brief 技能安装包

B 站收藏夹批量处理技能：把一个收藏夹里的全部视频批量生成「知识卡 + 章节全文 + 总报告 HTML」，
支持断点续跑，产出可离线阅读的本地文件。

本仓库即安装包，用于在新电脑上一键安装该技能。

## 远程安装（推荐，从 GitHub 克隆）

```powershell
git clone https://github.com/gelanliuyue/bilibili-favorites-brief-skill.git
cd bilibili-favorites-brief-skill
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "D:\你的路径\bili-brief"
```

macOS / Linux：

```bash
git clone https://github.com/gelanliuyue/bilibili-favorites-brief-skill.git
cd bilibili-favorites-brief-skill
chmod +x install.sh && ./install.sh --project-root /Users/you/code/bili-brief
```

没有 git 时，用 GitHub 页面右上的 **Code → Download ZIP** 下载解压，再跑 `install.ps1`。
已装过旧版时 `git pull` 后重跑安装器即可；默认会把旧目录改名为 `.bak-时间戳` 保留，加 `-Force` 则直接覆盖。

## 包内结构

```
bilibili-favorites-brief-skill/
├─ bilibili-favorites-brief/     技能本体（可直接复制到任意 skills 目录）
│  ├─ SKILL.md                   技能定义（模型读取的入口）
│  ├─ config.example.json        配置模板
│  ├─ agents/openai.yaml         界面显示名与默认提示
│  ├─ references/                批次清单格式、专题教程模板
│  └─ scripts/
│     ├─ bili_favorites.py       主 CLI：list / run / status / resume / render
│     └─ render_report.py        HTML 报告与知识卡渲染
├─ install.ps1                   Windows 安装器
├─ install.sh                    macOS / Linux 安装器
├─ INSTALL.md                    详细安装与配置说明
└─ README.md                     本文件
```

## 最快安装方式（Windows）

1. 解压整个 zip。
2. 在解压目录打开 PowerShell，执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "D:\你的路径\bili-brief"
```

3. 脚本会把技能装到 `%USERPROFILE%\.workbuddy\skills` 和 `%USERPROFILE%\.codex\skills`，
   并生成该机器专属的 `config.json`。
4. 重启 Agent 应用（WorkBuddy / Codex），让其重新扫描技能目录。

只装到一个位置：

```powershell
.\install.ps1 -Target workbuddy -ProjectRoot "D:\你的路径\bili-brief"
.\install.ps1 -Target codex     -ProjectRoot "D:\你的路径\bili-brief"
```

## 必要前提（重要）

这个技能**不是纯离线工具**，它把重活交给本地 BiliBrief 后端。新电脑上必须同时具备：

| 依赖 | 要求 |
| --- | --- |
| BiliBrief 后端项目 | `project_root` 指向的目录，需含 `backend\.venv\Scripts\python.exe` |
| 后端服务 | 默认 `http://127.0.0.1:8483` 正在运行 |
| Python | 3.10+，且解释器能 `import markdown`（渲染报告用） |
| B 站登录态 | 在后端侧配置（Cookie 由后端解密管理），技能本身不接触凭据 |
| 模型 API Key | 在后端侧配置（默认 deepseek / deepseek-chat） |

缺少后端时，技能只能被安装，无法真正跑批。详见 `INSTALL.md`。

## 快速自检

装完后执行下面这条，能列出收藏夹名称说明链路已通（需要后端在跑）：

```powershell
& "<project_root>\backend\.venv\Scripts\python.exe" `
  "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\scripts\bili_favorites.py" `
  --config "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\config.json" list
```

其余命令与排错见 `INSTALL.md`。
