from __future__ import annotations

from typing import Any, Callable

import requests

from app.services.cookie_manager import CookieConfigManager
from app.utils.logger import get_logger


logger = get_logger(__name__)

FAVORITE_FOLDER_API = "https://api.bilibili.com/x/v3/fav/folder/created/list-all"
FAVORITE_RESOURCE_API = "https://api.bilibili.com/x/v3/fav/resource/list"
VIDEO_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BilibiliFavoritesError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BilibiliFavoritesClient:
    def __init__(
        self,
        *,
        cookie: str | None = None,
        http_get: Callable[..., Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.cookie = cookie if cookie is not None else CookieConfigManager().get("bilibili")
        self._http_get = http_get or requests.get
        self._timeout = timeout

    def list_created_folders(self) -> list[dict[str, Any]]:
        user_id = self._require_user_id()
        payload = self._get_json(
            FAVORITE_FOLDER_API,
            params={"up_mid": user_id, "type": 2},
            operation="list favorite folders",
        )
        data = payload.get("data") or {}
        folders = data.get("list") or []
        result = []
        for folder in folders:
            media_id = folder.get("id")
            if media_id is None:
                continue
            result.append(
                {
                    "media_id": int(media_id),
                    "title": str(folder.get("title") or ""),
                    "media_count": int(folder.get("media_count") or 0),
                    "cover": str(folder.get("cover") or ""),
                }
            )
        return result

    def list_folder_videos(
        self,
        media_id: int | str,
        *,
        author: str | None = None,
    ) -> dict[str, Any]:
        self._require_user_id()
        normalized_author = (author or "").strip()
        try:
            normalized_media_id = int(media_id)
        except (TypeError, ValueError) as exc:
            raise BilibiliFavoritesError(
                "favorite_folder_not_found",
                "收藏夹 ID 无效",
            ) from exc
        if normalized_media_id <= 0:
            raise BilibiliFavoritesError(
                "favorite_folder_not_found",
                "收藏夹 ID 无效",
            )

        videos: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        seen_bvids: set[str] = set()
        folder: dict[str, Any] = {
            "media_id": normalized_media_id,
            "title": "",
            "media_count": 0,
        }
        page_number = 1
        saw_media = False

        while True:
            params = {
                "media_id": normalized_media_id,
                "platform": "web",
                "pn": page_number,
                "ps": 20,
            }
            if normalized_author:
                params["keyword"] = normalized_author
            payload = self._get_json(
                FAVORITE_RESOURCE_API,
                params=params,
                operation="list favorite videos",
            )
            data = payload.get("data") or {}
            info = data.get("info") or {}
            if page_number == 1:
                folder = {
                    "media_id": int(info.get("id") or normalized_media_id),
                    "title": str(info.get("title") or ""),
                    "media_count": int(info.get("media_count") or 0),
                }

            medias = data.get("medias") or []
            saw_media = saw_media or bool(medias)
            for media in medias:
                bvid = str(media.get("bvid") or "").strip()
                item_type = media.get("type")
                if item_type != 2:
                    skipped.append(
                        {
                            "title": str(media.get("title") or ""),
                            "reason": "unsupported_type",
                            "raw_type": item_type,
                        }
                    )
                    continue
                if not bvid:
                    skipped.append(
                        {
                            "title": str(media.get("title") or ""),
                            "reason": "missing_bvid",
                            "raw_type": item_type,
                        }
                    )
                    continue
                if bvid in seen_bvids:
                    continue
                upper_name = str((media.get("upper") or {}).get("name") or "")
                if normalized_author and upper_name.casefold() != normalized_author.casefold():
                    continue
                seen_bvids.add(bvid)
                videos.append(
                    {
                        "bvid": bvid,
                        "title": str(media.get("title") or ""),
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "cover": str(media.get("cover") or ""),
                        "duration": int(media.get("duration") or 0),
                        "upper": upper_name,
                        "fav_time": int(media.get("fav_time") or 0),
                        "pub_time": int(
                            media.get("pubtime")
                            or media.get("ctime")
                            or media.get("fav_time")
                            or 0
                        ),
                        "available": True,
                    }
                )

            if not data.get("has_more"):
                break
            page_number += 1
            if page_number > 10_000:
                raise BilibiliFavoritesError(
                    "bilibili_favorites_unavailable",
                    "收藏夹分页超过安全上限",
                )

        if not saw_media:
            raise BilibiliFavoritesError(
                "favorite_folder_empty",
                "收藏夹为空或没有可读取内容",
            )

        return {
            "folder": folder,
            "videos": videos,
            "skipped": skipped,
            "total": len(videos),
        }

    def list_video_pages(self, bvid: str) -> dict[str, Any]:
        self._require_user_id()
        normalized_bvid = str(bvid or "").strip()
        if not normalized_bvid:
            raise BilibiliFavoritesError(
                "favorite_folder_not_found",
                "视频 BV 号无效",
            )
        payload = self._get_json(
            VIDEO_VIEW_API,
            params={"bvid": normalized_bvid},
            operation="list video pages",
        )
        data = payload.get("data") or {}
        pages = data.get("pages") or []
        normalized_pages = []
        for index, page in enumerate(pages, 1):
            page_number = int(page.get("page") or index)
            normalized_pages.append(
                {
                    "page": page_number,
                    "part": str(page.get("part") or f"P{page_number}"),
                    "duration": int(page.get("duration") or 0),
                    "cid": int(page.get("cid") or 0),
                    "url": (
                        "https://www.bilibili.com/video/"
                        f"{normalized_bvid}?p={page_number}"
                    ),
                }
            )
        if not normalized_pages:
            normalized_pages.append(
                {
                    "page": 1,
                    "part": str(data.get("title") or normalized_bvid),
                    "duration": int(data.get("duration") or 0),
                    "cid": int(data.get("cid") or 0),
                    "url": f"https://www.bilibili.com/video/{normalized_bvid}",
                }
            )
        normalized_pages.sort(key=lambda page: page["page"])
        return {
            "bvid": str(data.get("bvid") or normalized_bvid),
            "title": str(data.get("title") or normalized_bvid),
            "pages": normalized_pages,
        }

    def _require_user_id(self) -> str:
        if not self.cookie:
            logger.info("Bilibili Cookie is not configured")
            raise BilibiliFavoritesError(
                "bilibili_login_required",
                "请先扫码登录 B 站",
            )
        user_id = self._cookie_value("DedeUserID")
        if not user_id or not self._cookie_value("SESSDATA"):
            logger.info("Bilibili login cookie is incomplete")
            raise BilibiliFavoritesError(
                "bilibili_login_required",
                "请先扫码登录 B 站",
            )
        return user_id

    def _cookie_value(self, name: str) -> str:
        if not self.cookie:
            return ""
        for pair in self.cookie.split(";"):
            key, separator, value = pair.strip().partition("=")
            if separator and key == name:
                return value
        return ""

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Referer": "https://www.bilibili.com/",
            "Cookie": self.cookie or "",
        }

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        try:
            response = self._http_get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload = response if isinstance(response, dict) else response.json()
        except Exception as exc:
            logger.warning("Unable to %s: %s", operation, type(exc).__name__)
            raise BilibiliFavoritesError(
                "bilibili_favorites_unavailable",
                "暂时无法读取 B 站收藏夹，请稍后重试",
            ) from exc

        if not isinstance(payload, dict):
            raise BilibiliFavoritesError(
                "bilibili_favorites_unavailable",
                "B 站收藏夹返回了异常数据",
            )

        api_code = payload.get("code")
        if api_code == 0:
            return payload
        if api_code in {-101, -111, 61000}:
            logger.warning("Bilibili favorite request rejected: code=%s", api_code)
            raise BilibiliFavoritesError(
                "bilibili_login_required",
                "B 站登录已失效，请重新扫码",
            )
        if api_code in {-403, 403}:
            logger.warning("Bilibili favorite request forbidden: code=%s", api_code)
            raise BilibiliFavoritesError(
                "favorite_folder_forbidden",
                "无法访问这个收藏夹",
            )
        if api_code in {-400, -404, 404}:
            logger.warning("Bilibili favorite not found: code=%s", api_code)
            raise BilibiliFavoritesError(
                "favorite_folder_not_found",
                "收藏夹不存在或已经删除",
            )
        logger.warning("Bilibili favorite request failed: code=%s", api_code)
        raise BilibiliFavoritesError(
            "bilibili_favorites_unavailable",
            "暂时无法读取 B 站收藏夹，请稍后重试",
        )
