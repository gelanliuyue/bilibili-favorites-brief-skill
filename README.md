# bilibili-favorites-brief 技能安装包 + BiliBrief 服务端

B 站收藏夹批量处理：把一个收藏夹里的全部视频批量生成「知识卡 + 章节全文 + 总报告 HTML」，
支持断点续跑，产出可离线阅读的本地文件。

本仓库同时包含两部分，一台干净电脑 clone 下来即可完整部署：

| 部分 | 位置 | 作用 |
| --- | --- | --- |
| 技能 | `bilibili-favorites-brief/` | 装进 WorkBuddy / Codex，负责编排与产物整理 |
| 服务端 | `server/` | BiliBrief 后端（FastAPI）+ 前端源码与 dist，真正干活的一方 |

## 完整部署（新电脑，两步）

```powershell
git clone https://github.com/gelanliuyue/bilibili-favorites-brief-skill.git
cd bilibili-favorites-brief-skill

# 第一步：部署服务端（建 venv、装依赖、生成 .env、检查 ffmpeg）
powershell -ExecutionPolicy Bypass -File .\deploy.ps1

# 第二步：把技能装到 Agent，指向刚部署的服务端
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "$PWD\server"
```

macOS / Linux 对应 `./deploy.sh` 与 `./install.sh --project-root "$PWD/server"`。

`-ProjectRoot` 必须指向 `server`，不是仓库根：技能会去 `<project_root>\backend\.venv` 找解释器。
完整步骤、前置条件、排错见 **[DEPLOY.md](DEPLOY.md)**。

## 只装技能（已有可用的 BiliBrief 服务端）

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "D:\已有路径\bili-brief"
```

技能默认连 `http://127.0.0.1:8483`，只装一处用 `-Target workbuddy` 或 `-Target codex`。

## 仓库结构

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
├─ server/                       BiliBrief 服务端（MIT，BiliNote 快照）
│  ├─ backend/                   FastAPI 后端
│  ├─ BillNote_frontend/         前端源码 + 已构建 dist
│  ├─ BillNote_extension/        浏览器扩展
│  ├─ docker-compose.yml         容器化部署（可选）
│  └─ UPSTREAM.md                上游来源与提交号
├─ deploy.ps1 / deploy.sh        服务端一键部署
├─ install.ps1 / install.sh      技能一键安装
├─ DEPLOY.md                     完整部署说明（服务端 + 技能）
├─ INSTALL.md                    技能侧详细说明
└─ README.md                     本文件
```

## 必要前提（重要）

技能本身不含模型与凭据，重活都在本地服务端：

| 依赖 | 要求 |
| --- | --- |
| Python | 3.10–3.12（3.13 部分轮子缺失） |
| ffmpeg | 必需，未装则任务必然失败 |
| 服务端 | 默认 `http://127.0.0.1:8483` 运行中 |
| B 站登录态 | 在服务端界面扫码登录，Cookie 由后端加密保存 |
| 模型 API Key | 在服务端设置页填写（默认 deepseek / deepseek-chat） |

前端只是配置登录态与 API Key 的界面，技能本身只依赖后端 8483 端口。

## 快速自检

装完后执行下面这条，能列出收藏夹名称说明链路已通（需要服务端在跑）：

```powershell
& "<project_root>\backend\.venv\Scripts\python.exe" `
  "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\scripts\bili_favorites.py" `
  --config "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\config.json" list
```

## 许可与来源

服务端为 [BiliNote](https://github.com/JefferyHcool/BiliNote)（提交 `90940fd`）的 MIT 快照，
许可证保留在 `server/LICENSE`。仓库不含 `.env`、数据库、venv、node_modules 与 ffmpeg 二进制，
这些均由 `deploy.ps1` 或首次运行自动生成。
