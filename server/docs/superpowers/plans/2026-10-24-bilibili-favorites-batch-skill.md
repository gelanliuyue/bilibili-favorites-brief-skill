# BiliBrief 收藏夹批量知识卡 Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let WorkBuddy/Codex process a complete Bilibili favorite folder through the local BiliBrief backend, with resumable per-video knowledge cards and a final collection report.

**Architecture:** Add two read-only FastAPI endpoints for the logged-in user's favorite folders and complete video pagination. A standalone Codex skill will call those endpoints, serialize existing single-video jobs, persist a local manifest, resume incomplete work, export Markdown/HTML cards, and render a collection report.

**Tech Stack:** Python 3, FastAPI, requests, unittest, Markdown, vanilla HTML/CSS/JavaScript, Markmap CDN with nested-list fallback.

**Spec:** `docs/superpowers/specs/2026-10-24-bilibili-favorites-batch-skill-design.md`

## Global Constraints

- Process only the current logged-in user's created video favorites; never mutate favorites.
- Keep `SESSDATA`, Cookie headers, QR keys, and model API keys out of API responses and logs.
- Page through every favorite result with `ps=20`; do not cap a full-folder batch.
- Process one video at a time and persist each task ID before polling.
- Final batch status must be exactly one of `SUCCESS`, `PARTIAL`, `FAILED`, or `CANCELLED`.
- Resume must not repeat successful videos.
- Output only under `%USERPROFILE%\Documents\BiliBrief` by default.
- No WeChat integration, public sharing, local LLM, or new batch web UI.
- Run backend tests with `.venv\Scripts\python.exe -m unittest ...` from `backend/`.
- Use apply_patch for source edits and conventional commit messages.

## Review Focus

- The favorites collection changes while pages are read: deduplicate by BV while preserving the first-seen order.
- The Cookie is missing, expired, or belongs to another user: return a structured login-required error before creating a batch.
- The process restarts after submitting a task but before polling finishes: resume the same task ID rather than submit a duplicate.
- A video result is marked successful but its saved result file is missing: mark the item failed and include it in the final partial report.
- A favorite/video title contains Windows-illegal characters or collides with an existing batch: sanitize safely and create a new timestamped directory.

---

### Task 1: Read Bilibili favorite folders and complete video pages

**Files:**
- Create: `backend/app/services/bilibili_favorites.py`
- Test: `backend/tests/test_bilibili_favorites.py`

**Interfaces:**
- Consumes: `CookieConfigManager.get("bilibili") -> str | None`
- Produces: `BilibiliFavoritesError(code: str, message: str)`
- Produces: `BilibiliFavoritesClient.list_created_folders() -> list[dict]`
- Produces: `BilibiliFavoritesClient.list_folder_videos(media_id: int | str) -> dict`
- Folder shape: `{"media_id": int, "title": str, "media_count": int, "cover": str}`
- Video shape: `{"bvid": str, "title": str, "url": str, "cover": str, "duration": int, "upper": str, "fav_time": int, "available": true}`
- Skipped shape: `{"title": str, "reason": str, "raw_type": int | None}`

- [ ] **Step 1: Write failing service tests**

Add tests covering:

```python
client = BilibiliFavoritesClient(cookie="SESSDATA=secret; DedeUserID=42", http_get=fake_get)
folders = client.list_created_folders()
assert folders == [{"media_id": 1001, "title": "产品", "media_count": 2, "cover": "cover"}]
```

```python
result = client.list_folder_videos(1001)
assert [video["bvid"] for video in result["videos"]] == ["BV1", "BV2", "BV3"]
assert [item["reason"] for item in result["skipped"]] == ["unsupported_type", "missing_bvid"]
```

The fake HTTP function returns page 1 with `has_more=true` and page 2 with `has_more=false`; include one duplicate BV. Also test the missing-Cookie path raises `BilibiliFavoritesError(code="bilibili_login_required")`, and that exception/log text never includes the Cookie value.

- [ ] **Step 2: Run the service test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_favorites -v
```

Expected: import failure because `app.services.bilibili_favorites` does not exist.

- [ ] **Step 3: Implement the favorite API client**

Use `requests.Session` by default and inject `http_get` for tests. Read `SESSDATA`/`DedeUserID` from the Cookie header, set Referer and User-Agent, check Bilibili JSON `code == 0`, paginate `resource/list`, deduplicate by `bvid`, and separate invalid entries into `skipped`.

Map failures to:

- `bilibili_login_required`
- `favorite_folder_not_found`
- `favorite_folder_forbidden`
- `favorite_folder_empty`
- `bilibili_favorites_unavailable`

- [ ] **Step 4: Run the service test and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_favorites -v
```

Expected: all service tests pass; output contains no Cookie value.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/bilibili_favorites.py backend/tests/test_bilibili_favorites.py
git commit -m "feat: read bilibili favorite folders"
```

---

### Task 2: Expose read-only favorite routes

**Files:**
- Create: `backend/app/routers/bilibili_favorites.py`
- Modify: `backend/app/__init__.py`
- Test: `backend/tests/test_bilibili_favorites_routes.py`

**Interfaces:**
- Consumes: `BilibiliFavoritesClient` and `BilibiliFavoritesError` from Task 1.
- Produces: `GET /api/bilibili_auth/favorites -> ResponseWrapper`
- Produces: `GET /api/bilibili_auth/favorites/{media_id}/videos -> ResponseWrapper`
- Success payloads match Task 1 shapes.

- [ ] **Step 1: Write failing route tests**

Create a FastAPI test app with the new router and inject a fake client. Assert:

```python
assert folders.json()["data"][0]["title"] == "产品"
assert videos.json()["data"]["videos"][0]["bvid"] == "BV1"
```

Assert invalid `media_id` returns HTTP 422, login-required returns business code `40101`, and no response text contains `SESSDATA`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_favorites_routes -v
```

Expected: import failure because the router does not exist.

- [ ] **Step 3: Implement router and registration**

Add a router with `prefix="/bilibili_auth"` and injectable client factory. Convert expected `BilibiliFavoritesError` instances to `ResponseWrapper.error`; use business code `40101` for login-required and keep unexpected failures generic without secret data. Register the router in `backend/app/__init__.py`.

- [ ] **Step 4: Run route and service tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_favorites tests.test_bilibili_favorites_routes -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/routers/bilibili_favorites.py backend/app/__init__.py backend/tests/test_bilibili_favorites_routes.py
git commit -m "feat: expose bilibili favorite routes"
```

---

### Task 3: Implement batch manifest state and safe paths

**Files:**
- Create: `skills/bilibili-favorites-brief/scripts/bili_favorites.py`
- Create: `backend/tests/test_bili_favorites_skill_state.py`
- Create: `skills/bilibili-favorites-brief/references/batch-manifest.md`

**Interfaces:**
- Produces: `safe_name(value: str) -> str`
- Produces: `create_batch_dir(output_root: Path, folder_title: str, now: datetime | None = None) -> Path`
- Produces: `load_manifest(batch_dir: Path) -> dict`
- Produces: `write_manifest(batch_dir: Path, manifest: dict) -> None`
- Produces: `next_pending_items(manifest: dict) -> list[dict]`
- Produces: `batch_status(items: list[dict]) -> str`

- [ ] **Step 1: Write failing state tests**

Test:

```python
assert safe_name('产品/经理:入门?') == '产品_经理_入门_'
assert batch_status([{"state": "success"}, {"state": "failed"}]) == "PARTIAL"
assert batch_status([{"state": "success"}, {"state": "skipped"}]) == "SUCCESS"
assert batch_status([{"state": "failed"}, {"state": "skipped"}]) == "FAILED"
```

Test atomic manifest writes, `running` items being returned for resume, and two batches with the same title receiving distinct timestamped directories.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_skill_state -v
```

Expected: module/function missing.

- [ ] **Step 3: Implement state helpers**

Use `pathlib`, `json`, `tempfile.NamedTemporaryFile`, and `os.replace`. Persist schema version, folder metadata, provider/model, created/updated timestamps, and ordered item records. Do not store credentials.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_skill_state -v
```

Expected: all state tests pass.

- [ ] **Step 5: Document manifest schema**

Record exact item states: `pending`, `running`, `success`, `failed`, `skipped`; include a compact JSON example and recovery rules.

- [ ] **Step 6: Commit**

```powershell
git add skills/bilibili-favorites-brief/scripts/bili_favorites.py skills/bilibili-favorites-brief/references/batch-manifest.md backend/tests/test_bili_favorites_skill_state.py
git commit -m "feat: add resumable favorites batch state"
```

---

### Task 4: Submit, poll, and resume BiliBrief video tasks

**Files:**
- Modify: `skills/bilibili-favorites-brief/scripts/bili_favorites.py`
- Create: `backend/tests/test_bili_favorites_batch_runner.py`

**Interfaces:**
- Consumes: state helpers from Task 3.
- Produces: `BackendClient(base_url: str, opener: Callable = urllib.request.urlopen)`
- Produces: `BackendClient.health() -> dict`
- Produces: `BackendClient.login_status() -> dict`
- Produces: `BackendClient.list_folders() -> list[dict]`
- Produces: `BackendClient.list_videos(media_id: int) -> dict`
- Produces: `BackendClient.submit(video: dict, provider_id: str, model_name: str, task_id: str | None) -> str`
- Produces: `BackendClient.task(task_id: str) -> dict`
- Produces: `run_batch(batch_dir: Path, client: BackendClient, provider_id: str, model_name: str, poll_seconds: float = 5.0) -> dict`

- [ ] **Step 1: Write failing runner tests**

Use a fake `BackendClient` with scripted states:

```python
result = run_batch(batch_dir, fake_client, "deepseek", "deepseek-chat", poll_seconds=0)
assert result["status"] == "PARTIAL"
assert manifest["items"][0]["state"] == "success"
assert manifest["items"][1]["task_id"] == "retry-task"
```

Cover:

- new item: submit -> task ID persisted -> success;
- running resume: poll stored task ID and never resubmit;
- failure continues to later items;
- login-required or missing provider fails before any submission;
- successful item missing `<task_id>.json` becomes `failed` with `result_file_missing`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_batch_runner -v
```

Expected: functions missing.

- [ ] **Step 3: Implement the backend client**

Use only Python standard library HTTP calls. Parse `ResponseWrapper`; treat nonzero `code` as an error object preserving code/message/data. Add timeouts and no retry for authentication/configuration errors.

- [ ] **Step 4: Implement serial batch execution**

For each ordered item, persist state before and after external actions. Submit with the manifest item's stable `task_id`; poll until `SUCCESS` or `FAILED`; stop with a fatal status on login/configuration errors; continue on individual video failures. Copy successful result JSON and Markdown into the item directory.

- [ ] **Step 5: Run runner tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_skill_state tests.test_bili_favorites_batch_runner -v
```

Expected: all state and runner tests pass.

- [ ] **Step 6: Commit**

```powershell
git add skills/bilibili-favorites-brief/scripts/bili_favorites.py backend/tests/test_bili_favorites_batch_runner.py
git commit -m "feat: run resumable bilibrief video batches"
```

---

### Task 5: Render knowledge cards and collection reports

**Files:**
- Create: `skills/bilibili-favorites-brief/scripts/render_report.py`
- Modify: `skills/bilibili-favorites-brief/scripts/bili_favorites.py`
- Test: `backend/tests/test_bili_favorites_rendering.py`

**Interfaces:**
- Consumes: manifest and per-video `result.json` from Task 4.
- Produces: `render_video_card(result: dict, destination: Path) -> None`
- Produces: `render_batch_report(manifest: dict, destination: Path) -> None`
- Produces: CLI `render --batch-dir <path>`

- [ ] **Step 1: Write failing rendering tests**

Create a temporary manifest with one success, one failed, and one skipped item. Assert rendered outputs contain:

```python
assert "一句话结论" in card_html
assert "知识卡" in card_html
assert "失败项" in report_html
assert "已跳过" in report_html
assert "视频标题" in report_html
```

Also assert HTML escaping prevents a title containing `<script>` from becoming executable markup.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_rendering -v
```

Expected: renderer functions missing.

- [ ] **Step 3: Implement card and report rendering**

Use the `markdown` package for Markdown-to-HTML, escape metadata, and create responsive printable pages. Include per-video metadata, source link, summary sections, and a Markmap container with a nested-list fallback. Reports must visibly separate successes, failures, and skipped items and summarize counts.

- [ ] **Step 4: Add deterministic report index generation**

When the batch finishes, write `总报告.md` with count summary, ordered video index, one-line conclusions extracted from Markdown, and explicit failure/skip tables. Leave a section titled `跨视频分析` for Codex/WorkBuddy to complete from the saved summaries.

- [ ] **Step 5: Run rendering tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_rendering -v
```

Expected: all rendering tests pass.

- [ ] **Step 6: Commit**

```powershell
git add skills/bilibili-favorites-brief/scripts/render_report.py skills/bilibili-favorites-brief/scripts/bili_favorites.py backend/tests/test_bili_favorites_rendering.py
git commit -m "feat: render favorites cards and reports"
```

---

### Task 6: Package and validate the Codex skill

**Files:**
- Create: `skills/bilibili-favorites-brief/SKILL.md`
- Create: `skills/bilibili-favorites-brief/agents/openai.yaml`
- Create: `skills/bilibili-favorites-brief/config.example.json`
- Modify: `skills/bilibili-favorites-brief/scripts/bili_favorites.py`
- Test: `backend/tests/test_bili_favorites_skill_cli.py`

**Interfaces:**
- Produces CLI:
  - `list`
  - `run --folder <name>`
  - `run --media-id <id>`
  - `resume --batch-dir <path>`
  - `status --batch-dir <path>`
  - `render --batch-dir <path>`
- Produces local config fields: `project_root`, `backend_url`, `output_root`, `provider_id`, `model_name`.

- [ ] **Step 1: Write failing CLI tests**

Use temporary config and a fake local HTTP endpoint. Assert:

- `list` prints folder titles but no Cookie;
- `run --folder` stops before submission when login is false;
- `status` reports `PARTIAL` without rewriting state;
- invalid arguments exit nonzero with an actionable message;
- default output root resolves to `%USERPROFILE%\Documents\BiliBrief`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bili_favorites_skill_cli -v
```

Expected: CLI entry functions missing or behavior absent.

- [ ] **Step 3: Implement CLI and configuration**

Read local config from the skill directory, allow CLI overrides, and never print credentials. Before a batch, show folder title, total processable videos, skipped count, provider/model, and output directory. Require an explicit `--yes` for batches above zero to prevent accidental API spend.

- [ ] **Step 4: Write `SKILL.md`**

The skill must instruct Codex/WorkBuddy to:

1. list folders when the requested name is ambiguous;
2. show batch size and API-cost warning;
3. call the script rather than reimplementing HTTP flow;
4. wait for batch completion;
5. read all per-video summaries and fill `跨视频分析`;
6. re-run `render` after writing the analysis;
7. report actual `SUCCESS`/`PARTIAL`/`FAILED`, file paths, and failures.

The description must trigger for Bilibili favorite/folder batch knowledge-card/report requests and exclude generic single-video or WeChat bot requests.

- [ ] **Step 5: Add UI metadata and validate**

Create `agents/openai.yaml` with a concise display name and default prompt. Run:

```powershell
py -3 <skills-root>\.system\skill-creator\scripts\quick_validate.py skills\bilibili-favorites-brief
```

If `py` is unavailable, run the validator with the Codex runtime Python and record the exact command used. Expected: validation passes.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bilibili_favorites tests.test_bilibili_favorites_routes tests.test_bili_favorites_skill_state tests.test_bili_favorites_batch_runner tests.test_bili_favorites_rendering tests.test_bili_favorites_skill_cli -v
```

Expected: all focused tests pass.

- [ ] **Step 7: Install the skill into Codex**

Copy the validated source directory to:

```text
C:\Users\<user>\.codex\skills\bilibili-favorites-brief
```

Create its local `config.json` pointing to:

```json
{
  "project_root": "C:\\path\\to\\bili-brief",
  "backend_url": "http://127.0.0.1:8483",
  "output_root": "C:\\Users\\<user>\\Documents\\BiliBrief",
  "provider_id": "deepseek",
  "model_name": "deepseek-chat"
}
```

Do not overwrite an unrelated existing skill. If the target already exists, compare and update only this skill's files.

- [ ] **Step 8: Commit**

```powershell
git add skills/bilibili-favorites-brief backend/tests/test_bili_favorites_skill_cli.py
git commit -m "feat: package bilibili favorites brief skill"
```

---

### Task 7: Verify with a real logged-in favorite folder

**Files:**
- No source changes expected.
- Output: `%USERPROFILE%\Documents\BiliBrief\<favorite>_<timestamp>\`

**Interfaces:**
- Consumes all previous tasks.

- [ ] **Step 1: Confirm prerequisites**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8483/api/sys_health
Invoke-RestMethod http://127.0.0.1:8483/api/bilibili_auth/status
Invoke-RestMethod http://127.0.0.1:8483/api/get_all_providers
```

Expected: backend/ffmpeg/db are `ok`; Bilibili login is true; at least one DeepSeek/Qwen Key is configured. If login is false, stop and ask the user to rescan rather than proceeding.

- [ ] **Step 2: List and choose a small real folder**

Run the installed skill CLI `list`. Ask the user to choose a folder containing 2-3 videos for the first real run. Do not print unrelated private folder contents beyond titles needed for selection.

- [ ] **Step 3: Run one small batch and inspect every artifact**

Run idempotently until the small batch finishes. Verify:

- each successful item has `result.json`, `摘要.md`, and `知识卡.html`;
- `batch_summary.json` matches individual states;
- `总报告.md` and `总报告.html` list success, failure, and skipped items;
- every Bilibili source link uses the correct BV.

- [ ] **Step 4: Verify resume behavior**

Create a copy of the completed batch manifest with one fake pending item, run `resume`, and confirm successful items are not submitted again. Remove the copy afterward with verified path checks.

- [ ] **Step 5: Report actual outcome**

Report exact counts, paths, remaining failures, and whether the skill is ready for a full folder. Do not call it complete if any required artifact or resume check fails.

---

### Task 8: Final regression and handoff

**Files:**
- No new files expected.

**Interfaces:**
- Consumes all implementation and validation tasks.

- [ ] **Step 1: Run focused backend tests**

Run the full focused command from Task 6.

- [ ] **Step 2: Run broader backend discovery and report unrelated failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Known unrelated failures currently exist in `test_task_serial_executor`, `test_url_normalize`, and `test_ydl_retry_opts`; report their current status rather than hiding them or claiming the whole suite is green.

- [ ] **Step 3: Validate the installed skill**

Run the skill validator against both source and installed copies. Confirm the installed `SKILL.md` description mentions Bilibili favorite/folder batch processing and excludes generic WeChat-bot use.

- [ ] **Step 4: Verify git state and summarize**

Run:

```powershell
git status --short
git log --oneline -10
```

The worktree must be clean. Report commit IDs, installation path, output path, test evidence, and remaining user actions.
