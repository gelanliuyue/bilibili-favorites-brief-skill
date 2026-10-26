from fastapi import APIRouter, Query

from app.services.bilibili_favorites import (
    BilibiliFavoritesClient,
    BilibiliFavoritesError,
)
from app.utils.response import ResponseWrapper as R


router = APIRouter(prefix="/bilibili_auth", tags=["Bilibili favorites"])

BUSINESS_CODES = {
    "bilibili_login_required": 40101,
    "favorite_folder_not_found": 40401,
    "favorite_folder_forbidden": 40301,
    "favorite_folder_empty": 20401,
    "bilibili_favorites_unavailable": 50301,
}


@router.get("/favorites")
def list_favorites():
    try:
        return R.success(BilibiliFavoritesClient().list_created_folders())
    except BilibiliFavoritesError as exc:
        return R.error(
            msg=exc.message,
            code=BUSINESS_CODES.get(exc.code, 50301),
            data={"reason": exc.code},
        )
    except Exception:
        return R.error(
            msg="暂时无法读取 B 站收藏夹，请稍后重试",
            code=500,
            data={"reason": "bilibili_favorites_unavailable"},
        )


@router.get("/favorites/{media_id}/videos")
def list_favorite_videos(
    media_id: int,
    author: str | None = Query(default=None),
):
    try:
        return R.success(
            BilibiliFavoritesClient().list_folder_videos(
                media_id,
                author=author,
            )
        )
    except BilibiliFavoritesError as exc:
        return R.error(
            msg=exc.message,
            code=BUSINESS_CODES.get(exc.code, 50301),
            data={"reason": exc.code},
        )
    except Exception:
        return R.error(
            msg="暂时无法读取 B 站收藏夹，请稍后重试",
            code=500,
            data={"reason": "bilibili_favorites_unavailable"},
        )


@router.get("/videos/{bvid}/pages")
def list_video_pages(bvid: str):
    try:
        return R.success(BilibiliFavoritesClient().list_video_pages(bvid))
    except BilibiliFavoritesError as exc:
        return R.error(
            msg=exc.message,
            code=BUSINESS_CODES.get(exc.code, 50301),
            data={"reason": exc.code},
        )
    except Exception:
        return R.error(
            msg="暂时无法读取视频分 P，请稍后重试",
            code=500,
            data={"reason": "bilibili_favorites_unavailable"},
        )
