# 完整部署说明（服务端 + 技能）

本仓库 = 技能安装包 + 可运行的 BiliBrief 服务端源码快照。
一台干净的电脑上，`git clone` 之后按本文档两步即可跑通：**先部署服务端，再安装技能**。

## 一、仓库结构

```
bilibili-favorites-brief-skill/
├─ bilibili-favorites-brief/   技能本体（安装到 Agent 的 skills 目录）
├─ server/                     BiliBrief 服务端（BiliNote 快照，MIT）
│  ├─ backend/                 FastAPI 后端（技能真正调用的部分）
│  │  ├─ app/                  业务代码
│  │  ├─ config/               后端配置
│  │  ├─ tests/                测试
│  │  ├─ main.py               入口，默认监听 127.0.0.1:8483
│  │  ├─ requirements.txt      Python 依赖（已锁定版本）
│  │  ├─ .env.example          环境变量模板
│  │  └─ ffmpeg_helper.py      ffmpeg 定位逻辑
│  ├─ BillNote_frontend/       前端源码 + 已构建的 dist/
│  ├─ serve_web.py             本地托管前端（静态 + /api 反代，零依赖，替代 http.server）
│  ├─ BillNote_extension/      浏览器扩展
│  ├─ skills/                  项目内技能副本（后端测试引用此路径，与仓库根技能同源）
│  ├─ docker-compose.yml       容器化部署（可选）
│  ├─ LICENSE                  MIT
│  └─ UPSTREAM.md              上游来源与提交号
├─ deploy.ps1 / deploy.sh      服务端一键部署
├─ install.ps1 / install.sh    技能一键安装
├─ DEPLOY.md                   本文档
├─ INSTALL.md                  技能侧详细说明
└─ README.md
```

## 二、前置条件

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| Python | 3.10 / 3.11 / 3.12 | 3.13 上 `onnxruntime`、`ctranslate2` 等轮子可能缺失，建议 3.12 |
| ffmpeg | 必需 | 音视频下载与切片，未装则任务必然失败 |
| 磁盘 | 约 3 GB | 依赖约 1.2 GB + 模型缓存 + 运行产物 |
| Node.js | 可选 | 只在需要重新构建前端时需要；仓库已带 `dist/` |
| 网络 | 能访问 B 站与模型 API | 首次下载 faster-whisper 模型会占用额外空间 |

ffmpeg 三种获取方式（任选其一）：

```powershell
winget install --id Gyan.FFmpeg -e                     # Windows
brew install ffmpeg                                     # macOS
sudo apt install ffmpeg                                 # Debian/Ubuntu
```

或者下载后把 `ffmpeg.exe`、`ffprobe.exe` 放进 `server\backend\tools\ffmpeg\`，
或在 `server\backend\.env` 里写 `FFMPEG_BIN_PATH=D:\ffmpeg\bin`（目录，不是 exe 路径）。

> `winget install` 装完之后**当前终端/新进程的 PATH 往往还没刷新**，直接跑后端会说找不到 ffmpeg。
> `deploy.ps1` 会主动去 winget / scoop / chocolatey 的落点找 `ffmpeg.exe`，找到就写进 `.env` 的
> `FFMPEG_BIN_PATH`，所以不用重开终端。

## 三、第一步：部署服务端

### Windows

```powershell
git clone https://github.com/gelanliuyue/bilibili-favorites-brief-skill.git
cd bilibili-favorites-brief-skill
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

脚本依次做：校验 Python 版本 → 建 `server\backend\.venv` → 按 `requirements.txt` 安装依赖
（含 `setuptools<81` 兜底与 import 冒烟测试）→ 生成 `server\backend\.env`（已存在则不覆盖）→
定位 ffmpeg 并写入 `FFMPEG_BIN_PATH` → 汇报前端 `dist` 状态。

依赖安装需要几分钟，中途不要中断。装完启动后端：

```powershell
cd server\backend
.\.venv\Scripts\python.exe main.py
```

看到 `Starting server on 0.0.0.0:8483` 即成功。

常用参数：

| 参数 | 用途 |
| --- | --- |
| `-Start` | 装完直接启动后端 |
| `-Recreate` | 删掉旧 venv 重装（依赖装坏时用） |
| `-BuildFrontend` | 用 npm/pnpm 重新构建前端（需 Node） |
| `-SkipInstall` | 只建 venv 和 .env，不装依赖 |

### macOS / Linux

```bash
git clone https://github.com/gelanliuyue/bilibili-favorites-brief-skill.git
cd bilibili-favorites-brief-skill
chmod +x deploy.sh && ./deploy.sh
# 或直接启动：./deploy.sh --start
```

## 四、第二步：安装技能

服务端跑起来之后，把技能装进 Agent：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "<仓库绝对路径>\server"
```

例：`-ProjectRoot "C:\Users\you\bilibili-favorites-brief-skill\server"`。

这一步会写入 `config.json`：

```json
{
  "project_root": "<仓库>\\server",
  "backend_url": "http://127.0.0.1:8483",
  "output_root": "<用户目录>\\Documents\\BiliBrief",
  "provider_id": "deepseek",
  "model_name": "deepseek-chat"
}
```

`project_root` 必须指向本项目根（脚本会去 `<project_root>\backend\.venv` 找解释器、
到 `<project_root>\backend\note_results` 取任务产物），所以填 `server`，不要填仓库根。

## 五、首次使用要配的两件事

后端跑起来后，打开前端界面（见下一节）完成：

1. **B 站登录**：设置页扫码登录，Cookie 由后端加密保存到 `server\backend\data\`，不入库、不外传。
2. **模型 API Key**：设置页填入 DeepSeek（或其它 provider）的 Key，点测试连接。

这两项都保存在本机，仓库里没有任何凭据。

## 六、前端怎么跑

技能本身不依赖前端（只依赖后端 8483 端口），前端只是用来扫码登录和填 API Key 的界面。

**方式一（零构建，推荐）**：仓库自带 `server\BillNote_frontend\dist`，用仓库里的
`server\serve_web.py` 托管。它同时做静态托管和 `/api` 反代，等价于生产环境的 nginx 那一层：

```powershell
cd server
.\backend\.venv\Scripts\python.exe serve_web.py            # 默认 http://127.0.0.1:3015
# 后端换了端口时：serve_web.py --backend http://127.0.0.1:9000
```

只用 Python 标准库，不需要装依赖。它负责三件事：

1. 托管 `dist`，并把 `/api`、`/static` 反代到后端 8483。前端 axios 的 baseURL 是相对路径
   `/api`，只有同源反代能把它正确送达后端。
2. SPA 回落：直接刷新 `/brief/setup` 这类深链时返回 `index.html`，不会 404。
3. 反代时禁用上游 gzip，避免响应体被浏览器当文本解析导致「业务失败」误报。

> **不要用 `python -m http.server` 托管 dist。** 它没有 `/api` 反代，前端的
> `GET /api/sys_check` 会打到静态服务器自己身上（404），60 秒后弹「后端启动失败」，
> 并连带出现「暂时无法读取后端模型配置」「操作失败，请稍后再试」这类误报。

**方式二（开发模式）**：

```powershell
cd server\BillNote_frontend
npm install
npm run dev          # 默认 3015，vite 自带 /api 代理
```

**方式三（重新构建）**：`.\deploy.ps1 -BuildFrontend`，产物覆盖 `dist/`。

## 七、运行时目录（自动生成，不入库）

| 路径 | 内容 |
| --- | --- |
| `server\backend\data\` | SQLite 库、向量库、加密后的凭据 |
| `server\backend\note_results\` | 每个任务的生成结果 JSON（技能从这里读） |
| `server\backend\uploads\` | 上传的音视频临时文件 |
| `server\backend\logs\` | 运行日志 |
| `server\backend\static\screenshots\` | 截图输出 |

备份要备份 `data\`；`note_results\` 可随时重建（会重新消耗额度）。

## 八、关键 .env 项

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` | `8483` | 改端口后必须同步改技能 `config.json` 的 `backend_url`，以及前端 `serve_web.py --backend` |
| `BACKEND_HOST` | `0.0.0.0` | 只本机用可改 `127.0.0.1` |
| `API_BASE_URL` | `http://127.0.0.1` | **只填 scheme+host，不要带端口**（代码会拼上 `BACKEND_PORT`） |
| `DATA_DIR` | `data` | 相对 `backend/` 目录 |
| `FFMPEG_BIN_PATH` | 空 | ffmpeg 所在目录，留空则从 PATH 查找 |
| `TRANSCRIBER_TYPE` | `fast-whisper` | 也可 `bcut` / `kuaishou`（云端 ASR） |
| `WHISPER_MODEL_SIZE` | `base` | 首次运行会下载模型 |

## 九、排错

| 现象 | 原因与处理 |
| --- | --- |
| `pip install` 卡在 onnxruntime / chromadb / torch | 换 Python 3.12；国内网络可先 `pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` |
| 后端启动报 `No module named 'pkg_resources'`，或 `import ctranslate2` 失败 | `setuptools` 版本太新（≥81 已移除 `pkg_resources`）。`requirements.txt` 已锁 `setuptools<81`，旧环境执行 `pip install "setuptools<81"` 修复。**注意不要反过来去升级 setuptools** |
| 后端启动报 `No module named 'app'` | 没在 `server\backend` 目录下执行 `main.py` |
| 技能报 `python interpreter is missing` | `-ProjectRoot` 填成了仓库根。应为 `...\server`（新版 `install.ps1` 会自动纠正并提示） |
| 技能连不上后端 | 后端没起，或端口不是 8483，或 `config.json` 里 `backend_url` 未更新 |
| 任务失败并提示 ffmpeg | ffmpeg 未安装，或装了但 PATH 未刷新（刚 `winget install` 常见）。`deploy.ps1` 会自动找到 winget 目录并写入 `FFMPEG_BIN_PATH`；手工排查用 `where ffmpeg` |
| 前端打开 60 秒后弹「后端启动失败」 | 用了没有 `/api` 反代的静态服务器（如 `python -m http.server`）。改用 `server\serve_web.py` |
| 点保存 API Key 弹「操作失败，请稍后再试」，顶部提示「暂时无法读取后端模型配置」 | 同上，`/api` 没送达后端；或反代去掉了 `Content-Encoding` 却转发压缩体（响应被当文本解析）。用 `serve_web.py` 即可。**若后端日志 `logs\app.log` 里有 `Provider updated successfully`，说明 Key 其实已写入**，只是前端没读回响应 |
| 刷新子页面（如 `/brief/setup`）出现 404 | 静态托管缺 SPA 回落。`serve_web.py` 已处理 |
| 访问 `127.0.0.1` 报 502 或 hang | 本机装了全局 HTTP 代理且没有 localhost 例外。`serve_web.py` 内部已绕过；命令行排查时加 `--noproxy '*'` 或 `NO_PROXY='*'` |
| 改了 `BACKEND_PORT` 后前端连不上 | 启动前端要带 `--backend http://127.0.0.1:<新端口>`，技能侧改 `config.json` 的 `backend_url` |
| 401 / 需要扫码 | B 站登录态失效，回设置页重新扫码 |

## 十、来源与许可

- 服务端为 [BiliNote](https://github.com/JefferyHcool/BiliNote) 的快照（提交 `90940fde4d224d0f69ad99674f4af0a1ea52d3c4`），MIT 许可，`server/LICENSE` 已保留，`server/UPSTREAM.md` 记录了来源。
- 本仓库在原项目基础上增加了 BiliBrief 移动端界面、brief 提示词风格、字幕优先提交预检、R1 测试，以及技能与部署脚本。

**未打包的内容**（体积或安全原因）：`.venv/`、`node_modules/`、`backend/data/`、`note_results/`、`uploads/`、`logs/`、
`backend/tools/ffmpeg/`（约 161 MB 二进制）、`backend/.env`（真实密钥）、任何 SQLite 库、`server/doc/`（上游截图与微信群二维码，约 7 MB，与部署无关）。
这些都由 `deploy.ps1` 或首次运行自动生成；`server/doc/` 可从上游 BiliNote 仓库获取。
