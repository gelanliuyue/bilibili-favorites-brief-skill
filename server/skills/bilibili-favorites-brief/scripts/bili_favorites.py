#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SCHEMA_VERSION = 1
RESUMABLE_STATES = {"pending", "running", "failed"}
SUCCESS_STATES = {"SUCCESS"}
FAILED_STATES = {"FAILED"}
MAX_POLL_SECONDS = 6 * 60 * 60
RESULT_FILE_GRACE_SECONDS = 10.0
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value))
    cleaned = cleaned.strip(" .")
    if not cleaned:
        return "untitled"
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned[:100]


def create_batch_dir(
    output_root: Path,
    folder_title: str,
    now: datetime | None = None,
) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    base_name = f"{safe_name(folder_title)}_{timestamp}"
    for suffix in range(1, 10_000):
        name = base_name if suffix == 1 else f"{base_name}_{suffix}"
        candidate = root / name
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("Unable to allocate a unique batch directory")


def load_manifest(batch_dir: Path) -> dict[str, Any]:
    path = Path(batch_dir) / "manifest.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Batch manifest must be a JSON object")
    return payload


def write_manifest(batch_dir: Path, manifest: dict[str, Any]) -> None:
    target_dir = Path(batch_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "manifest.json"
    payload = dict(manifest)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target_dir,
            prefix="manifest-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def next_pending_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in manifest.get("items", [])
        if item.get("state") in RESUMABLE_STATES
    ]


def batch_status(items: list[dict[str, Any]]) -> str:
    states = [str(item.get("state") or "") for item in items]
    successes = states.count("success")
    failures = states.count("failed") + states.count("skipped")
    active = states.count("pending") + states.count("running")
    if active:
        return "IN_PROGRESS"
    if successes and not failures:
        return "SUCCESS"
    if successes:
        return "PARTIAL"
    return "FAILED"


def sort_video_items(
    videos: list[dict[str, Any]],
    order: str = "oldest",
) -> list[dict[str, Any]]:
    if order == "favorite":
        return list(videos)
    if order not in {"oldest", "newest"}:
        raise ValueError(f"Unsupported video order: {order}")
    def sort_key(video: dict[str, Any]) -> tuple[Any, ...]:
        published = int(video.get("pub_time") or video.get("fav_time") or 0)
        if order == "newest":
            published = -published
        return (
            published,
            str(video.get("parent_bvid") or video.get("bvid") or ""),
            int(video.get("page") or 1),
        )

    ordered = sorted(videos, key=sort_key)
    return ordered


def expand_video_pages(
    videos: list[dict[str, Any]],
    page_loader,
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for video in videos:
        page_data = page_loader(str(video["bvid"]))
        pages = sorted(
            page_data.get("pages") or [],
            key=lambda page: int(page.get("page") or 1),
        )
        if not pages:
            expanded.append({**video, "page": 1})
            continue
        parent_title = str(page_data.get("title") or video.get("title") or video["bvid"])
        if len(pages) == 1:
            expanded.append(
                {
                    **video,
                    "page": 1,
                    "part": pages[0].get("part") or parent_title,
                    "cid": pages[0].get("cid"),
                }
            )
            continue
        for page in pages:
            page_number = int(page.get("page") or 1)
            part = str(page.get("part") or f"P{page_number}")
            expanded.append(
                {
                    **video,
                    "bvid": video["bvid"],
                    "parent_bvid": video["bvid"],
                    "parent_title": parent_title,
                    "page": page_number,
                    "part": part,
                    "cid": page.get("cid"),
                    "title": f"{parent_title} - p{page_number:02d} {part}",
                    "url": (
                        f"https://www.bilibili.com/video/{video['bvid']}"
                        f"?p={page_number}"
                    ),
                    "duration": int(page.get("duration") or 0),
                }
            )
    return expanded


def item_output_id(item: dict[str, Any]) -> str:
    bvid = str(item.get("bvid") or "")
    page = int(item.get("page") or 1)
    if item.get("parent_bvid") or page > 1:
        return f"{bvid}_p{page:02d}"
    return bvid


class BackendRequestError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class BackendClient:
    def __init__(
        self,
        base_url: str,
        opener=urlopen,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener = opener
        self._timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("/api/sys_health")

    def login_status(self) -> dict[str, Any]:
        return self._request("/api/bilibili_auth/status")

    def list_folders(self) -> list[dict[str, Any]]:
        return self._request("/api/bilibili_auth/favorites")

    def list_videos(
        self,
        media_id: int,
        author: str | None = None,
    ) -> dict[str, Any]:
        path = f"/api/bilibili_auth/favorites/{int(media_id)}/videos"
        if author:
            path += f"?{urlencode({'author': author})}"
        return self._request(path)

    def video_pages(self, bvid: str) -> dict[str, Any]:
        return self._request(f"/api/bilibili_auth/videos/{bvid}/pages")

    def providers(self) -> list[dict[str, Any]]:
        return self._request("/api/get_all_providers")

    def provider_configured(self, provider_id: str) -> bool:
        for provider in self.providers():
            if provider.get("id") != provider_id:
                continue
            api_key = str(provider.get("api_key") or "")
            return bool(api_key and set(api_key) != {"*"})
        return False

    def submit(
        self,
        video: dict[str, Any],
        provider_id: str,
        model_name: str,
        task_id: str | None,
    ) -> str:
        payload = {
            "video_url": video["url"],
            "provider_id": provider_id,
            "model_name": model_name,
            "platform": "bilibili",
            "quality": "medium",
            "format": ["link", "summary"],
            "style": "brief",
            "screenshot": False,
            "video_understanding": False,
            "video_interval": 0,
            "grid_size": [],
        }
        if task_id:
            payload["task_id"] = task_id
        data = self._request("/api/generate_note", method="POST", payload=payload)
        submitted_id = str((data or {}).get("task_id") or "")
        if not submitted_id:
            raise BackendRequestError(500, "后端没有返回任务 ID")
        return submitted_id

    def task(self, task_id: str) -> dict[str, Any]:
        return self._request(f"/api/task_status/{task_id}")

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            try:
                envelope = json.loads(raw.decode("utf-8"))
            except Exception:
                raise BackendRequestError(exc.code, f"HTTP {exc.code}") from exc
            raise BackendRequestError(
                int(envelope.get("code") or exc.code),
                str(envelope.get("msg") or f"HTTP {exc.code}"),
                envelope.get("data"),
            ) from exc
        except Exception as exc:
            raise BackendRequestError(-1, "无法连接 BiliBrief 后端") from exc

        try:
            envelope = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise BackendRequestError(500, "后端返回了无法解析的数据") from exc
        if not isinstance(envelope, dict):
            raise BackendRequestError(500, "后端返回了异常数据")
        code = int(envelope.get("code") or 0)
        if code != 0:
            raise BackendRequestError(
                code,
                str(envelope.get("msg") or "后端请求失败"),
                envelope.get("data"),
            )
        return envelope.get("data")


def run_batch(
    batch_dir: Path,
    client: BackendClient,
    provider_id: str,
    model_name: str,
    poll_seconds: float = 5.0,
) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    manifest = load_manifest(batch_dir)
    manifest["provider"] = {"id": provider_id, "model": model_name}

    fatal_reason = _preflight(client, provider_id)
    if fatal_reason:
        _skip_unprocessed(manifest, fatal_reason)
        write_manifest(batch_dir, manifest)
        return _write_batch_summary(batch_dir, manifest, fatal_reason=fatal_reason)

    result_root = Path(manifest["project_root"]) / "backend" / "note_results"
    videos_root = batch_dir / "videos"
    videos_root.mkdir(exist_ok=True)

    for item in manifest["items"]:
        if item.get("state") in {"success", "skipped"}:
            continue
        if not item.get("task_id"):
            item["state"] = "running"
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["message"] = ""
            write_manifest(batch_dir, manifest)

        try:
            if not item.get("task_id"):
                item["task_id"] = client.submit(
                    item,
                    provider_id,
                    model_name,
                    None,
                )
                write_manifest(batch_dir, manifest)
            elif item.get("state") == "failed":
                item["state"] = "running"
                item["attempts"] = int(item.get("attempts") or 0) + 1
                item["message"] = "正在重试"
                write_manifest(batch_dir, manifest)
                item["task_id"] = client.submit(
                    item,
                    provider_id,
                    model_name,
                    item["task_id"],
                )
                write_manifest(batch_dir, manifest)

            task = _poll_task(client, item["task_id"], poll_seconds)
            if str(task.get("status")) in FAILED_STATES:
                raise BackendRequestError(
                    500,
                    str(task.get("message") or "视频任务失败"),
                )
            if str(task.get("status")) not in SUCCESS_STATES:
                raise BackendRequestError(
                    500,
                    f"未知任务状态: {task.get('status')}",
                )

            source_result = result_root / f"{item['task_id']}.json"
            if not _wait_for_file(source_result, RESULT_FILE_GRACE_SECONDS):
                raise FileNotFoundError("result_file_missing")
            result = json.loads(source_result.read_text(encoding="utf-8"))
            item_dir = videos_root / item_output_id(item)
            _save_item_result(item_dir, result)
            _render_video_card(item_dir, result, item)
            item["state"] = "success"
            item["message"] = ""
        except FileNotFoundError as exc:
            item["state"] = "failed"
            item["message"] = str(exc) or "result_file_missing"
        except BackendRequestError as exc:
            if _is_fatal_request_error(exc):
                item["state"] = "failed"
                item["message"] = exc.message
                _skip_unprocessed(manifest, "batch_stopped")
                write_manifest(batch_dir, manifest)
                return _write_batch_summary(
                    batch_dir,
                    manifest,
                    fatal_reason=_fatal_code(exc),
                )
            item["state"] = "failed"
            item["message"] = exc.message
        except Exception as exc:
            item["state"] = "failed"
            item["message"] = str(exc) or type(exc).__name__
        write_manifest(batch_dir, manifest)

    return _write_batch_summary(batch_dir, manifest)


def _preflight(client: BackendClient, provider_id: str) -> str:
    if not provider_id:
        return "provider_not_configured"
    try:
        client.health()
    except BackendRequestError:
        return "backend_unavailable"
    try:
        login = client.login_status()
    except BackendRequestError:
        return "bilibili_login_required"
    if not login.get("logged_in"):
        return "bilibili_login_required"
    try:
        provider_configured = client.provider_configured(provider_id)
    except BackendRequestError:
        return "provider_check_failed"
    if not provider_configured:
        return "provider_not_configured"
    return ""


def _poll_task(
    client: BackendClient,
    task_id: str,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + MAX_POLL_SECONDS
    while True:
        task = client.task(task_id)
        if str(task.get("status")) in SUCCESS_STATES | FAILED_STATES:
            return task
        if time.monotonic() >= deadline:
            raise TimeoutError("视频任务等待超时")
        time.sleep(max(0.0, poll_seconds))


def _wait_for_file(path: Path, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        if path.is_file():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def _save_item_result(destination: Path, result: dict[str, Any]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = str(result.get("markdown") or "")
    if not markdown:
        raise FileNotFoundError("result_file_missing")
    (destination / "摘要.md").write_text(markdown, encoding="utf-8")


def _render_video_card(
    destination: Path,
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    from render_report import render_video_card

    render_video_card(
        result,
        destination / "知识卡.html",
        source_url=str(item.get("url") or ""),
    )


def _skip_unprocessed(manifest: dict[str, Any], reason: str) -> None:
    for item in manifest.get("items", []):
        if item.get("state") in {"pending", "running"} and not item.get("task_id"):
            item["state"] = "skipped"
            item["message"] = reason


def _is_fatal_request_error(exc: BackendRequestError) -> bool:
    message = exc.message.lower()
    return exc.code == 40101 or any(
        token in message
        for token in ("未登录", "扫码登录", "api key 未配置", "api key未配置")
    )


def _fatal_code(exc: BackendRequestError) -> str:
    return (
        "bilibili_login_required"
        if exc.code == 40101 or "登录" in exc.message
        else "provider_not_configured"
    )


def _write_batch_summary(
    batch_dir: Path,
    manifest: dict[str, Any],
    *,
    fatal_reason: str = "",
) -> dict[str, Any]:
    items = manifest.get("items", [])
    summary = {
        "status": batch_status(items),
        "fatal_reason": fatal_reason,
        "counts": {
            state: sum(1 for item in items if item.get("state") == state)
            for state in ("success", "failed", "skipped", "pending", "running")
        },
        "batch_dir": str(batch_dir),
    }
    target = batch_dir / "batch_summary.json"
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    from render_report import render_batch_report

    render_batch_report(manifest, batch_dir / "总报告.html")
    return summary


def default_output_root() -> Path:
    home = os.environ.get("USERPROFILE") or str(Path.home())
    return Path(home) / "Documents" / "BiliBrief"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path or os.environ.get("BILIBRIEF_SKILL_CONFIG") or "")
    if not path and not os.environ.get("BILIBRIEF_SKILL_CONFIG"):
        config_path = Path(__file__).resolve().parents[1] / "config.json"
    if not config_path.is_file():
        raise ValueError(
            f"Skill config not found: {config_path}. "
            "Copy config.example.json to config.json and update its paths."
        )
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Skill config must be a JSON object")
    data.setdefault("backend_url", "http://127.0.0.1:8483")
    data.setdefault("output_root", str(default_output_root()))
    data.setdefault("provider_id", "deepseek")
    data.setdefault("model_name", "deepseek-chat")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bili-favorites-brief",
        description="Batch Bilibili favorite folders through local BiliBrief.",
    )
    parser.add_argument("--config", help="Path to the skill config JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List the current account's favorite folders")

    run_parser = subparsers.add_parser("run", help="Start a new favorite batch")
    folder_group = run_parser.add_mutually_exclusive_group(required=True)
    folder_group.add_argument("--folder", help="Exact favorite folder title")
    folder_group.add_argument("--media-id", type=int, help="Favorite folder media_id")
    run_parser.add_argument("--provider", help="Model provider ID")
    run_parser.add_argument("--model", help="Model name")
    run_parser.add_argument("--author", help="Only process videos from this exact UP name")
    run_parser.add_argument(
        "--sort",
        choices=("oldest", "newest", "favorite"),
        default="oldest",
        help="Video order; default: oldest first",
    )
    run_parser.add_argument("--yes", action="store_true", help="Confirm API usage")

    resume_parser = subparsers.add_parser("resume", help="Resume a saved batch")
    resume_parser.add_argument("--batch-dir", required=True)
    resume_parser.add_argument("--provider")
    resume_parser.add_argument("--model")
    resume_parser.add_argument("--yes", action="store_true", help="Confirm API usage")

    status_parser = subparsers.add_parser("status", help="Show a saved batch status")
    status_parser.add_argument("--batch-dir", required=True)

    render_parser = subparsers.add_parser("render", help="Regenerate batch HTML reports")
    render_parser.add_argument("--batch-dir", required=True)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    client_factory=BackendClient,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        client = client_factory(str(config["backend_url"]))
        if args.command == "list":
            return _cmd_list(client)
        if args.command == "status":
            return _cmd_status(Path(args.batch_dir))
        if args.command == "render":
            return _cmd_render(Path(args.batch_dir))
        if args.command == "run":
            return _cmd_run(args, config, client)
        if args.command == "resume":
            return _cmd_resume(args, config, client)
        parser.error("Unknown command")
    except BackendRequestError as exc:
        print(f"BiliBrief 后端错误：{exc.message}", file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"操作失败：{exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_list(client: BackendClient) -> int:
    login = client.login_status()
    if not login.get("logged_in"):
        print("B 站尚未登录，请先在 BiliBrief 设置页扫码登录。", file=sys.stderr)
        return 2
    folders = client.list_folders()
    if not folders:
        print("当前账号没有自建视频收藏夹。")
        return 0
    for folder in folders:
        print(
            f"{folder.get('media_id')}\t{folder.get('title') or '未命名'}"
            f"\t{folder.get('media_count') or 0} 个"
        )
    return 0


def _cmd_run(args, config: dict[str, Any], client: BackendClient) -> int:
    health = client.health()
    if health.get("backend") != "ok":
        print("BiliBrief 后端未就绪。", file=sys.stderr)
        return 2
    login = client.login_status()
    if not login.get("logged_in"):
        print("B 站尚未登录，请先在 BiliBrief 设置页扫码登录。", file=sys.stderr)
        return 2

    if args.media_id is not None:
        media_id = int(args.media_id)
    else:
        matching = [
            folder
            for folder in client.list_folders()
            if str(folder.get("title")) == args.folder
        ]
        if len(matching) != 1:
            print(
                f"找不到唯一匹配的收藏夹：{args.folder}。请先运行 list 查看名称。",
                file=sys.stderr,
            )
            return 2
        media_id = int(matching[0]["media_id"])

    payload = client.list_videos(media_id, author=args.author)
    videos = expand_video_pages(
        payload.get("videos") or [],
        client.video_pages,
    )
    videos = sort_video_items(videos, args.sort)
    skipped = payload.get("skipped") or []
    provider_id = args.provider or config["provider_id"]
    model_name = args.model or config["model_name"]
    output_root = Path(config["output_root"])
    author_line = f"作者筛选：{args.author}\n" if args.author else ""
    print(
        f"收藏夹：{(payload.get('folder') or {}).get('title') or media_id}\n"
        f"{author_line}"
        f"可处理：{len(videos)} 个；跳过：{len(skipped)} 个\n"
        f"模型：{provider_id} / {model_name}\n"
        f"输出目录：{output_root}"
    )
    if not args.yes:
        print("这是确认预览，尚未提交。确认额度消耗后请加 --yes 重新运行。")
        return 0
    if not client.provider_configured(provider_id):
        print("模型 API Key 未配置，请先在 BiliBrief 设置页保存并测试连接。", file=sys.stderr)
        return 2

    folder_title = str((payload.get("folder") or {}).get("title") or f"收藏夹-{media_id}")
    batch_dir = create_batch_dir(output_root, folder_title)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(config["project_root"]),
        "folder": payload.get("folder") or {"media_id": media_id, "title": folder_title},
        "provider": {"id": provider_id, "model": model_name},
        "filter": {"author": args.author} if args.author else {},
        "sort": args.sort,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                **video,
                "state": "pending",
                "attempts": 0,
                "message": "",
            }
            for video in videos
        ]
        + [
            {
                "bvid": "",
                "title": item.get("title") or "失效收藏",
                "state": "skipped",
                "attempts": 0,
                "message": item.get("reason") or "skipped",
            }
            for item in skipped
        ],
    }
    write_manifest(batch_dir, manifest)
    summary = run_batch(batch_dir, client, provider_id, model_name)
    _print_summary(summary)
    return 0 if summary["status"] in {"SUCCESS", "PARTIAL"} else 2


def _cmd_resume(args, config: dict[str, Any], client: BackendClient) -> int:
    batch_dir = Path(args.batch_dir)
    manifest = load_manifest(batch_dir)
    provider = manifest.get("provider") or {}
    provider_id = args.provider or provider.get("id") or config["provider_id"]
    model_name = args.model or provider.get("model") or config["model_name"]
    if not args.yes:
        pending = len(next_pending_items(manifest))
        print(f"待恢复：{pending} 个。确认继续请加 --yes。")
        return 0
    summary = run_batch(batch_dir, client, provider_id, model_name)
    _print_summary(summary)
    return 0 if summary["status"] in {"SUCCESS", "PARTIAL"} else 2


def _cmd_status(batch_dir: Path) -> int:
    manifest = load_manifest(batch_dir)
    items = manifest.get("items", [])
    result = {
        "status": batch_status(items),
        "batch_dir": str(batch_dir),
        "counts": {
            state: sum(1 for item in items if item.get("state") == state)
            for state in ("success", "failed", "skipped", "pending", "running")
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_render(batch_dir: Path) -> int:
    manifest = load_manifest(batch_dir)
    from render_report import render_batch_report, render_video_card

    for item in manifest.get("items", []):
        if item.get("state") != "success":
            continue
        bvid = str(item.get("bvid") or "")
        video_dir = batch_dir / "videos" / item_output_id(item)
        result = json.loads(
            (video_dir / "result.json").read_text(encoding="utf-8")
        )
        render_video_card(
            result,
            video_dir / "知识卡.html",
            source_url=str(
                item.get("url")
                or f"https://www.bilibili.com/video/{bvid}"
            ),
        )
    render_batch_report(manifest, batch_dir / "总报告.html")
    print(str(batch_dir / "总报告.html"))
    return 0


def _print_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
