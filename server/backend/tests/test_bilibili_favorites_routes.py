import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import bilibili_favorites
from app.services.bilibili_favorites import BilibiliFavoritesError


class FakeFavoritesClient:
    last_author = None

    def list_created_folders(self):
        return [
            {
                "media_id": 1001,
                "title": "产品",
                "media_count": 1,
                "cover": "cover",
            }
        ]

    def list_folder_videos(self, media_id, author=None):
        assert media_id == 1001
        type(self).last_author = author
        return {
            "folder": {"media_id": 1001, "title": "产品", "media_count": 1},
            "videos": [
                {
                    "bvid": "BV1",
                    "title": "第一集",
                    "url": "https://www.bilibili.com/video/BV1",
                    "cover": "cover",
                    "duration": 10,
                    "upper": "UP",
                    "fav_time": 1760000000,
                    "available": True,
                }
            ],
            "skipped": [],
            "total": 1,
        }

    def list_video_pages(self, bvid):
        assert bvid == "BV1"
        return {
            "bvid": "BV1",
            "title": "合集",
            "pages": [
                {
                    "page": 1,
                    "part": "第一集",
                    "duration": 10,
                    "cid": 1,
                    "url": "https://www.bilibili.com/video/BV1?p=1",
                }
            ],
        }


class LoginRequiredClient:
    def list_created_folders(self):
        raise BilibiliFavoritesError("bilibili_login_required", "请先扫码登录 B 站")


class SecretFailureClient:
    def list_created_folders(self):
        raise RuntimeError("SESSDATA=secret-session")


class BilibiliFavoritesRouteTests(unittest.TestCase):
    def setUp(self):
        FakeFavoritesClient.last_author = None
        self.app = FastAPI()
        self.app.include_router(bilibili_favorites.router, prefix="/api")
        self.client = TestClient(self.app)

    def test_lists_folders_and_videos(self):
        with patch.object(
            bilibili_favorites,
            "BilibiliFavoritesClient",
            FakeFavoritesClient,
        ):
            folders = self.client.get("/api/bilibili_auth/favorites")
            videos = self.client.get("/api/bilibili_auth/favorites/1001/videos")

        self.assertEqual(folders.status_code, 200)
        self.assertEqual(folders.json()["data"][0]["title"], "产品")
        self.assertEqual(videos.status_code, 200)
        self.assertEqual(videos.json()["data"]["videos"][0]["bvid"], "BV1")

    def test_login_required_has_structured_business_error(self):
        with patch.object(
            bilibili_favorites,
            "BilibiliFavoritesClient",
            LoginRequiredClient,
        ):
            response = self.client.get("/api/bilibili_auth/favorites")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 40101)
        self.assertIn("扫码登录", response.json()["msg"])

    def test_invalid_media_id_is_rejected_before_client_call(self):
        response = self.client.get("/api/bilibili_auth/favorites/not-a-number/videos")

        self.assertEqual(response.status_code, 422)

    def test_author_query_is_forwarded_to_the_favorite_client(self):
        with patch.object(
            bilibili_favorites,
            "BilibiliFavoritesClient",
            FakeFavoritesClient,
        ):
            response = self.client.get(
                "/api/bilibili_auth/favorites/1001/videos",
                params={"author": "测试UP主"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["total"], 1)
        self.assertEqual(FakeFavoritesClient.last_author, "测试UP主")

    def test_lists_video_pages(self):
        with patch.object(
            bilibili_favorites,
            "BilibiliFavoritesClient",
            FakeFavoritesClient,
        ):
            response = self.client.get("/api/bilibili_auth/videos/BV1/pages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pages"][0]["page"], 1)

    def test_unexpected_error_does_not_echo_secret_text(self):
        with patch.object(
            bilibili_favorites,
            "BilibiliFavoritesClient",
            SecretFailureClient,
        ):
            response = self.client.get("/api/bilibili_auth/favorites")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 500)
        self.assertNotIn("secret-session", response.text)


if __name__ == "__main__":
    unittest.main()
