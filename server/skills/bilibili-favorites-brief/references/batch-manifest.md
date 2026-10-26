# Batch manifest schema

`manifest.json` is the source of truth for a resumable BiliBrief favorite batch.
It contains metadata and ordered item states, never Cookie or API-key values.

```json
{
  "schema_version": 1,
  "folder": {"media_id": 1001, "title": "产品经理"},
  "provider": {"id": "deepseek", "model": "deepseek-chat"},
  "created_at": "2026-10-24T13:30:00+00:00",
  "updated_at": "2026-10-24T13:31:00+00:00",
  "items": [
    {
      "bvid": "BV1xxxxxxxxx",
      "title": "视频标题",
      "url": "https://www.bilibili.com/video/BV1xxxxxxxxx",
      "state": "running",
      "task_id": "uuid",
      "attempts": 1,
      "message": ""
    }
  ]
}
```

Item states:

- `pending`: not submitted yet.
- `running`: submitted; resume must poll the stored `task_id` instead of submitting again.
- `success`: result file exists and all required exports were written.
- `failed`: the task failed; a later resume may retry with the existing `task_id`.
- `skipped`: the favorite API returned a non-video, missing BV, or unavailable item.

Final batch states:

- `SUCCESS`: at least one success and no failed or skipped items.
- `PARTIAL`: at least one success and at least one failed or skipped item.
- `FAILED`: no successful items.
- `CANCELLED`: the user deliberately stopped the batch.

Writes are atomic: the manifest is written to a temporary file and replaced only
after the complete JSON document has reached disk.
