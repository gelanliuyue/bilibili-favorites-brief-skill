# 安装与配置说明

## 一、这个技能做什么

`bilibili-favorites-brief` 把一个 B 站收藏夹整批交给本地 BiliBrief 后端处理，逐条视频产出：

- `知识卡.html`：摘要 + 内嵌静态思维导图 + 章节全文
- `思维导图.svg`：独立静态图
- `摘要.md`、`章节全文.md`、`章节全文/`（按章节拆分的 Markdown）
- 收藏夹级 `总报告.md` / `总报告.html`

串行执行、每一步状态落盘，中断后可 `resume` 续跑，不会重复提交已成功的视频。

技能本身只负责编排；视频解析、ASR、模型调用、Cookie 解密全部在本地后端完成。

## 二、安装前必须准备好的东西

安装包只包含技能，**不包含后端程序**。新电脑上需要这三样：

1. **BiliBrief 后端项目目录**（下文记作 `<project_root>`）
   - 重装方式：把原来机器上的 bili-brief 项目（含 `backend/` 目录）复制过去，
     然后在 `<project_root>/backend` 下重建虚拟环境并装依赖：
     ```powershell
     cd <project_root>\backend
     python -m venv .venv
     .\.venv\Scripts\python.exe -m pip install -r requirements.txt
     .\.venv\Scripts\python.exe -m pip install markdown
     ```
   - 确认 `<project_root>\backend\.venv\Scripts\python.exe` 存在。
2. **后端配置**：`<project_root>/backend/.env`（模型 API Key 等）与 B 站登录态。
   这些凭据由后端管理，技能不会读取也不会打印。
3. **后端已启动**，默认监听 `http://127.0.0.1:8483`。
   启动方式：`cd <project_root>\backend` 后执行 `python main.py`（或项目自带的 `run.bat`）。

> 如果目标机器上没有 BiliBrief 项目，只装技能无法运行。这种情况下需要先迁移后端项目。

## 三、Windows 安装

### 1. 解压

把 `bilibili-favorites-brief-skill.zip` 解压到任意目录，例如 `D:\pkg\bilibili-favorites-brief-skill`。

### 2. 执行安装器

```powershell
cd D:\pkg\bilibili-favorites-brief-skill
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "D:\code\bili-brief"
```

安装器会依次做：

1. 校验包内文件完整；
2. 解析目标目录（默认同时装到 WorkBuddy 和 Codex 两个技能目录）；
3. 复制技能，若已有旧版则**自动改名为 `.bak-时间戳` 保留**（加 `-Force` 则直接覆盖）；
4. 写入该机器专属的 `config.json`；
5. 校验 Python 与 `markdown`、校验 CLI 可加载、探测后端端口；
6. 打印结果和下一步。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `-Target workbuddy` / `codex` / `both` / `custom` | 安装位置，默认 `both` |
| `-TargetDir <路径>` | `-Target custom` 时的具体目录 |
| `-ProjectRoot <路径>` | bili-brief 项目根目录，必填 |
| `-BackendUrl <url>` | 默认 `http://127.0.0.1:8483` |
| `-OutputRoot <路径>` | 批次产物根目录，默认 `%USERPROFILE%\Documents\BiliBrief` |
| `-PythonExe <路径>` | 指定解释器，默认取 `<ProjectRoot>\backend\.venv\Scripts\python.exe` |
| `-Force` | 覆盖已安装版本，不保留备份 |

例：

```powershell
# 只装 WorkBuddy，且强制覆盖
.\install.ps1 -Target workbuddy -ProjectRoot "D:\code\bili-brief" -Force

# 后端换端口
.\install.ps1 -ProjectRoot "D:\code\bili-brief" -BackendUrl "http://127.0.0.1:9000"
```

### 3. 不想用脚本时的手动安装

```powershell
Copy-Item -Recurse -Force .\bilibili-favorites-brief "$env:USERPROFILE\.workbuddy\skills\"
Copy-Item .\bilibili-favorites-brief\config.example.json "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\config.json"
```

然后手工编辑该 `config.json`，四个字段都要换成这台机器的真实路径：

```json
{
  "project_root": "D:\\code\\bili-brief",
  "backend_url": "http://127.0.0.1:8483",
  "output_root": "C:\\Users\\你的用户名\\Documents\\BiliBrief",
  "provider_id": "deepseek",
  "model_name": "deepseek-chat"
}
```

Windows 路径在 JSON 中必须用双反斜杠 `\\`。

## 四、macOS / Linux 安装

```bash
chmod +x install.sh
./install.sh --project-root /Users/you/code/bili-brief
# 只装一处：--target workbuddy | codex
# 覆盖：--force
```

说明：SKILL.md 里的调用示例是 PowerShell 写法。macOS/Linux 上直接用
`"<project_root>/backend/.venv/bin/python" "<skill_dir>/scripts/bili_favorites.py" --config "<skill_dir>/config.json" <子命令>` 即可，脚本本身是跨平台的纯标准库 Python（`render_report.py` 额外需要 `markdown`）。

## 五、安装后验证

在 PowerShell 里按顺序跑这三条，全部通过才算装好。

**1）CLI 能加载**

```powershell
& "<project_root>\backend\.venv\Scripts\python.exe" `
  "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\scripts\bili_favorites.py" --help
```

预期：打印 `list / run / resume / status / render` 五个子命令。

**2）后端通不通**

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8483/
```

预期：返回一个 HTTP 状态码（4xx 也算通，说明服务在监听）。

**3）真实拉一次收藏夹**

```powershell
& "<project_root>\backend\.venv\Scripts\python.exe" `
  "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\scripts\bili_favorites.py" `
  --config "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief\config.json" list
```

预期：列出收藏夹标题与视频数量。返回 401/凭证错误说明后端侧的 B 站登录态失效，需要在后端重新登录。

## 六、在对话里怎么触发

技能装好后重启应用，然后直接说：

- 「处理一下我的『产品经理』收藏夹，出知识卡和总报告」
- 「把 XX 收藏夹里某个 UP 主的视频单独跑一遍」

技能会先 `list` 让你选收藏夹，再跑一次**预演**（不提交）报出视频数、跳过数、模型、输出目录，
**只有你明确确认后才加 `--yes` 真正开始消耗 ASR 与模型额度**。

## 七、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 技能没被识别 | 目录层级错了。必须是 `<skills目录>\bilibili-favorites-brief\SKILL.md`，不能多套一层 |
| 报 `python interpreter is missing` | `config.json` 的 `project_root` 指向不对，或 venv 没建 |
| 报 `No module named markdown` | `pip install markdown` 到同一个解释器 |
| 连不上后端 | 后端没启动，或 `backend_url` 端口不符 |
| 401 / Cookie 相关错误 | 后端侧 B 站登录态失效，需在后端重新扫码登录 |
| 报告页样式错乱 | `render` 重跑即可：`... bili_favorites.py render --batch-dir "<批次目录>"` |

## 八、卸载

直接删掉技能目录即可，产物目录 `<output_root>` 不受影响：

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.workbuddy\skills\bilibili-favorites-brief"
```
