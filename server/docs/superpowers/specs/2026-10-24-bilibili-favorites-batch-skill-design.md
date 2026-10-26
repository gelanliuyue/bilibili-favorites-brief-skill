# BiliBrief 收藏夹批量知识卡 Skill 设计

## 状态

等待用户批准。批准后才进入实现计划。

## 目标

让用户在本机 WorkBuddy/Codex 中通过自然语言处理自己 B 站账号下的完整收藏夹。用户指定收藏夹后，Skill 读取全部视频，逐个调用现有 BiliBrief 生成知识卡，保存断点，并输出每个视频的知识卡和一份收藏夹总报告。

典型请求：

> 用 BiliBrief 处理我的收藏夹《产品经理》，做完整批次和汇总报告。

## 为什么做

用户已经在同一台 Windows 电脑上部署并验证 BiliBrief，B 站扫码登录、DeepSeek/千问 API、云端 BCut 转写和单视频知识卡生成均可工作。网页端适合临时查看单个视频；收藏夹通常有几十个视频，需要更适合批处理、断点恢复和汇总的入口。

不做微信自动化可以避免个人微信账号风险，同时让 WorkBuddy/Codex 直接操作本机应用。

## 范围

### 本次目标

1. 读取当前已登录账号创建的视频收藏夹。
2. 按收藏夹名称或 `media_id` 选择收藏夹。
3. 分页读取收藏夹中的全部视频，去重并保留收藏顺序。
4. 过滤非视频、已失效或没有 BV 号的条目，并在报告中明确列出跳过原因。
5. 逐个提交 BiliBrief 任务，不并发轰炸 B 站、BCut 和大模型接口。
6. 将任务状态、远端 task_id、视频信息和失败原因实时写入本地批次清单。
7. 中断后可继续，只重试未完成或失败项，不重复已完成项。
8. 每个成功视频输出 Markdown 摘要、独立 HTML 知识卡和原视频链接。
9. 批次结束后输出机器可读总清单和人类可读总报告。
10. 由 Codex/WorkBuddy 基于各视频摘要生成跨视频总结，包括共同主题、值得优先观看的视频和失败项。

### 非目标

- 不做微信机器人或微信消息监听。
- 不修改、删除或新增用户 B 站收藏夹内容。
- 不提供公网分享、账号系统或多用户隔离。
- 不实现完整的网页批量任务管理界面。
- 不自动购买或更换大模型 API、B 站账号。
- 不运行本地大模型。
- 不绕过 B 站登录、风控或会员权限。

### 明确失败条件

- B 站未登录或 Cookie 失效时，不开始批次，提示重新扫码。
- 模型 API Key 未配置时，不开始批次，提示完成设置。
- 收藏夹不存在、不可访问或没有视频时，不创建空成功批次。
- 某个视频失败时，批次可以继续，但最终状态必须是“部分成功”或“失败”，不能显示“全部完成”。
- 报告必须列出每个失败项和原因，不能静默省略。

## 约束

- 只在用户当前 Windows 电脑上运行，依赖本机 BiliBrief 后端和已加密保存的 B 站 Cookie。
- B 站收藏夹读取使用登录态 API；用户自建收藏夹需要有效 `SESSDATA`，用户 ID 从 Cookie 的 `DedeUserID` 获取。
- 收藏夹列表接口每页最多返回 20 个视频，必须完整分页。
- 全收藏夹可能需要数十分钟到数小时，并消耗 BCut/DeepSeek/千问额度；正式处理前必须展示数量和额度风险。
- 视频可能没有字幕，因此需要用户已经配置可用的云端 ASR；当前推荐 BCut。
- 收藏项可能包含已删除视频、非视频内容、失效稿件或重复 BV；这些项进入 `skipped`，不算静默丢失。
- Skill 不读取或展示 Cookie、API Key；所有敏感凭据只保留在后端。
- 生成结果必须留在本机，不自动上传到第三方存储。

## 方案选择

### 方案 A：后端全量批量系统 + 新网页

在 FastAPI 中增加持久化批次、后台队列、进度 API 和新的网页管理界面。

优点：网页体验完整，适合以后公开给更多用户。  
缺点：开发量最大，当前只需要个人 WorkBuddy 工作流，会引入不必要的任务队列和前端复杂度。

### 方案 B：后端薄适配 + Skill 编排

后端只增加收藏夹读取接口。Skill 脚本负责展开收藏夹、逐项提交现有单视频任务、保存本地 manifest、恢复断点、导出知识卡和生成报告。

优点：复用已验证的单视频流程，开发风险低；断点和报告数据由本地文件控制；以后仍可复用后端接口增加网页批量功能。  
缺点：批次运行依赖 Skill 脚本持续运行；不是完整的网页任务中心。

### 方案 C：Skill 直接访问所有 B 站与模型接口

Skill 自己读取 Cookie、调用 B 站、下载音频并调用模型。

优点：不改后端。  
缺点：重复实现登录、Cookie 解密、音视频处理和模型接口，凭据边界更差，也更容易与现有 BiliBrief 行为不一致。

### 选择

选择方案 B。它在“个人本机批处理”目标下最稳妥，并且保留以后扩展到网页批量管理的余地。

## 架构

### 1. B 站收藏夹后端适配

新增 `backend/app/services/bilibili_favorites.py`：

- 从现有 `CookieConfigManager` 获取 B 站 Cookie。
- 从 Cookie 中提取 `DedeUserID`，不把 Cookie 返回到响应。
- `list_created_folders()` 调用：
  - `GET https://api.bilibili.com/x/v3/fav/folder/created/list-all`
  - 参数：`up_mid`、`type=2`
- `list_videos(media_id)` 调用：
  - `GET https://api.bilibili.com/x/v3/fav/resource/list`
  - 参数：`media_id`、`platform=web`、`pn`、`ps=20`
  - 循环到 `has_more=false`
- 只把视频条目规范化为：

```json
{
  "bvid": "BV...",
  "title": "视频标题",
  "url": "https://www.bilibili.com/video/BV...",
  "cover": "https://...",
  "duration": 1234,
  "upper": "UP 主名称",
  "fav_time": 1760000000,
  "available": true
}
```

如接口返回不可用条目，保留条目元信息并标记 `available=false` 和 `skip_reason`。

新增路由：

- `GET /api/bilibili_auth/favorites`
  - 返回当前账号的自建收藏夹列表。
- `GET /api/bilibili_auth/favorites/{media_id}/videos`
  - 返回完整视频列表、总数、跳过项数量。

错误响应使用结构化业务错误：

- `bilibili_login_required`
- `favorite_folder_not_found`
- `favorite_folder_forbidden`
- `favorite_folder_empty`

### 2. Skill

新 Skill 目录：

```text
~/.codex/skills/bilibili-favorites-brief/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── bili_favorites.py
│   └── render_report.py
└── references/
    └── batch-manifest.md
```

`SKILL.md` 负责判断用户意图、选择收藏夹、确认批次规模、调用脚本、在批次结束后撰写跨视频报告。脚本负责可以确定性验证的工作，不依赖模型即兴重写流程。

`bili_favorites.py` 支持：

```text
list
run --folder "收藏夹名"
run --media-id 123456
resume --batch-dir "批次目录"
status --batch-dir "批次目录"
```

脚本行为：

1. 检查后端 `/api/sys_health`；后端未运行时给出可操作错误。
2. 检查 B 站登录状态和模型 API 配置。
3. 列出或解析目标收藏夹。
4. 创建批次目录和 `manifest.json`。
5. 一次只处理一个视频，按收藏顺序提交 `/api/generate_note`。
6. 立即把 task_id 写入 manifest，再轮询 `/api/task_status/{task_id}`。
7. 成功后保存后端结果并导出 Markdown/HTML；失败后记录原因并继续下一项。
8. `resume` 读取 manifest：
   - `success`：跳过并检查文件仍存在；
   - `running`：继续轮询原 task_id；
   - `failed`：使用原 task_id 重试；
   - `pending`：开始提交。
9. 最后写入 `batch_summary.json`，状态为：
   - `SUCCESS`：全部可处理视频成功；
   - `PARTIAL`：至少一个成功且有失败/跳过；
   - `FAILED`：没有成功项；
   - `CANCELLED`：用户主动停止。

### 3. 输出目录

默认输出根目录：

```text
%USERPROFILE%\Documents\BiliBrief
```

每次批次：

```text
<收藏夹名>_<YYYY-MM-DD_HHmm>/
├── manifest.json
├── batch_summary.json
├── 总报告.md
├── 总报告.html
├── videos/
│   └── <BV号>/
│       ├── result.json
│       ├── 摘要.md
│       └── 知识卡.html
└── logs/
    └── batch.log
```

文件夹和文件名移除 Windows 非法字符；重名批次使用时间戳区分，不覆盖旧批次。

### 4. HTML 知识卡与总报告

- `摘要.md` 原样保存 BiliBrief 返回的 Markdown。
- `知识卡.html` 使用独立静态页面展示标题、一句话结论、摘要、章节、术语和行动清单。
- 思维导图使用 Markmap；页面包含可读的嵌套列表作为 JavaScript 不可用时的降级内容。
- `总报告.md` 先由脚本生成确定性的批次统计和视频索引，再由 Codex/WorkBuddy 根据所有单视频摘要补充跨视频主题、优先级和行动建议。
- `总报告.html` 由 `render_report.py` 转成可打印页面，包含成功、失败和跳过项。

### 5. 模型和转写选择

- Skill 复用 BiliBrief 当前供应商配置，不另存 API Key。
- 如果只有一个已配置 API Key 的 DeepSeek/千问供应商，自动选择它和默认模型。
- 如果两个都已配置且用户未指定，Skill 只询问一次 provider/model，并把选择写入 Skill 的本机配置。
- 转写模式沿用 BiliBrief 当前设置；开始批次前确认模式不是不可用状态。
- 当前个人使用默认按顺序处理，不开放并发参数。

## 安全与隐私

- 收藏夹内容、视频标题、摘要和报告都属于用户隐私，默认只写到本机用户目录。
- Skill 日志不得包含 Cookie、SESSDATA、API Key、二维码 key。
- B 站 Cookie 只由后端解密和使用。
- 批次 manifest 不保存大模型响应中的完整密钥环境。
- 失败日志写入批次目录，方便后续恢复，但用户应知道该目录包含视频内容摘要。

## 测试策略

### 后端

- 未登录时返回 `bilibili_login_required`。
- 使用伪造的 API 分页响应验证完整分页、去重和顺序。
- 非视频、无 BV 和失效条目进入 skipped，不进入任务队列。
- 收藏夹不存在或不可访问时返回对应业务错误。
- 响应和日志不包含 Cookie。

### Skill 脚本

- 函数级测试覆盖 manifest 状态转换。
- 使用本地假 HTTP 服务验证提交、轮询、成功和失败继续。
- 中断后 `resume` 不重复已成功视频。
- `PARTIAL` 批次不会误报 `SUCCESS`。
- 文件名清理、重名批次和 JSON 原子写入。
- HTML 报告包含成功、失败和跳过项。

### 真实集成验证

1. 用户重新扫码登录 B 站。
2. 先选择一个包含 2-3 个视频的小收藏夹试跑。
3. 验证完整收藏夹展开、单个成功、单个失败继续和 resume。
4. 再处理一个真实完整收藏夹，确认总报告可打开且链接有效。

## 验收标准

- 在 WorkBuddy/Codex 中输入“处理我的收藏夹《名称》”，无需手工复制 BV。
- 能看到目标收藏夹总数、成功、失败和跳过数量。
- 每个成功视频都有 Markdown 和可独立打开的 HTML 知识卡。
- 每个失败视频都有明确原因，不阻塞后续视频。
- 中断后运行 `resume` 不重复生成已完成视频。
- 最终总报告能够列出整套收藏夹的观看优先级和共同主题。
- 全过程不暴露 Cookie 或 API Key。

## 已知前置问题

当前后端检索时 B 站状态为未登录，之前测试覆盖造成的假 Cookie 已暴露并修复测试隔离。正式集成验证前需要用户重新扫码登录。实现本身不读取旧 Cookie，也不会尝试绕过登录。
