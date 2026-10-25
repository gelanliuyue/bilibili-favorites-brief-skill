---
name: bilibili-favorites-brief
description: Process a complete Bilibili favorite folder through the local BiliBrief backend, producing resumable per-video knowledge cards and a collection-wide report. Use when the user asks to batch-process a Bilibili favorite folder, 收藏夹, or generate a knowledge-card report from all videos in one. Do not use for one-off Bilibili links, general note taking, or WeChat bot work.
---

# BiliBrief Favorite Folder Skill

Use the local scripts instead of reimplementing the BiliBrief HTTP flow. The
backend owns Bilibili Cookie decryption and model API keys; never ask for or
print those credentials.

## Locate runtime

Read the installed `config.json` in this skill directory. Run the CLI with the
Python environment recorded by the project:

```powershell
& "<project_root>\backend\.venv\Scripts\python.exe" `
  "<skill_dir>\scripts\bili_favorites.py" `
  --config "<skill_dir>\config.json" <arguments>
```

If the configured interpreter is missing, stop and report the missing path.
Do not switch to another Python silently.

## Workflow

### 1. Resolve the folder

If the user did not name a folder, run:

```powershell
... bili_favorites.py list
```

Show the returned folder titles and counts, then ask the user to choose. If the
name is ambiguous, list rather than guessing by partial name.

### 2. Preview the batch

Run `run --folder "<title>"` or `run --media-id <id>` without `--yes`. Add
`--author "<exact UP name>"` when the user wants only one creator's videos from
that folder. The default order is `--sort oldest`, which uses Bilibili publish
time; use `--sort newest` or `--sort favorite` only when requested.

Report:

- folder title;
- author filter, when supplied;
- processable video count;
- skipped count;
- provider/model;
- output directory;
- that every processable video can consume cloud ASR and model quota.

Do not start the paid batch until the user explicitly confirms. Then repeat the
same command with `--yes`.

### 3. Wait and supervise

Keep the command running until it exits. Do not claim progress from the initial
HTTP submission alone. The script serializes videos and persists every state
transition.

If interrupted or timed out:

- run `status --batch-dir "<path>"`;
- explain that `resume` continues stored task IDs;
- obtain confirmation for remaining paid work;
- run `resume --batch-dir "<path>" --yes`.

### 4. Complete the cross-video analysis

After the batch exits, read:

- `batch_summary.json`;
- `总报告.md`;
- every `videos/<BV>/摘要.md`.

Each successful item also contains the readable outputs:

- `知识卡.html`: summary, inline static mind map, and chapter full text;
- `思维导图.svg`: standalone static image;
- `章节全文.md`: every chapter paired with its full transcript;
- `章节全文/`: one Markdown file per chapter.

Edit the `## 跨视频分析` section in `总报告.md` with:

- shared themes and differences;
- recommended viewing order;
- the highest-value videos and why;
- concrete action suggestions;
- material gaps caused by failed or skipped items.

Do not invent content absent from the video summaries. Keep the analysis
grounded and cite video titles.

Then regenerate the HTML report:

```powershell
... bili_favorites.py render --batch-dir "<path>"
```

`render` rebuilds every successful video card, static SVG, chapter transcript,
and the collection report without calling the model again.

### 5. Report the real outcome

Read `batch_summary.json` again after rendering. Tell the user:

- `SUCCESS`, `PARTIAL`, or `FAILED`;
- exact success/failed/skipped counts;
- clickable local paths to `总报告.html` and each important card;
- every failed item and its message when the batch is partial or failed.

Never translate `PARTIAL` into “全部完成”. Never omit failed items.

## Recovery rules

- `pending`: submit normally.
- `running`: poll the existing `task_id`; never create a duplicate task.
- `failed`: retry with its existing `task_id`.
- `success`: skip unless required local files are missing.
- `skipped`: keep visible in the final report.

See [references/batch-manifest.md](references/batch-manifest.md) for the exact
schema and state meanings.

For a focused course guide or tutorial built from a subset of an existing batch,
read [references/focused-course-tutorial.md](references/focused-course-tutorial.md).
