import unittest

from app.services.bilibili_favorites import (
    BilibiliFavoritesClient,
    BilibiliFavoritesError,
)


COOKIE = "SESSDATA=secret-session; bili_jct=csrf; DedeUserID=42"


class BilibiliFavoritesServiceTests(unittest.TestCase):
    def test_lists_created_video_folders(self):
        calls = []

        def fake_get(url, *, params, headers, timeout):
            calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "id": 1001,
                            "fid": 1001,
                            "mid": 42,
                            "attr": 0,
                            "title": "产品",
                            "fav_state": 0,
                            "media_count": 2,
                            "cover": "cover",
                        }
                    ]
                },
            }

        client = BilibiliFavoritesClient(cookie=COOKIE, http_get=fake_get)

        folders = client.list_created_folders()

        self.assertEqual(
            folders,
            [{"media_id": 1001, "title": "产品", "media_count": 2, "cover": "cover"}],
        )
        self.assertEqual(calls[0]["params"], {"up_mid": "42", "type": 2})
        self.assertIn("SESSDATA=secret-session", calls[0]["headers"]["Cookie"])

    def test_pages_all_videos_deduplicates_and_skips_invalid_items(self):
        calls = []

        def media(index, title, bvid=None, item_type=2):
            value = {
                "id": 1000 + index,
                "type": item_type,
                "title": title,
                "cover": f"cover-{index}",
                "duration": index,
                "upper": {"mid": 7, "name": "UP"},
                "fav_time": 1760000000 + index,
                "link": f"bilibili://video/{bvid}" if bvid else "",
            }
            if bvid is not None:
                value["bvid"] = bvid
            return value

        def fake_get(_url, *, params, headers, timeout):
            calls.append({"params": params, "headers": headers, "timeout": timeout})
            if params["pn"] == 1:
                return {
                    "code": 0,
                    "data": {
                        "info": {"id": 1001, "title": "产品", "media_count": 4},
                        "medias": [
                            media(1, "第一集", "BV1"),
                            media(2, "专栏", item_type=12),
                        ],
                        "has_more": True,
                    },
                }
            return {
                "code": 0,
                "data": {
                    "info": {"id": 1001, "title": "产品", "media_count": 4},
                    "medias": [
                        media(3, "第二集", "BV2"),
                        media(4, "重复", "BV1"),
                        media(5, "缺少 BV"),
                        media(6, "第三集", "BV3"),
                    ],
                    "has_more": False,
                },
            }

        client = BilibiliFavoritesClient(cookie=COOKIE, http_get=fake_get)

        result = client.list_folder_videos(1001)

        self.assertEqual([video["bvid"] for video in result["videos"]], ["BV1", "BV2", "BV3"])
        self.assertEqual(
            [item["reason"] for item in result["skipped"]],
            ["unsupported_type", "missing_bvid"],
        )
        self.assertEqual([call["params"]["pn"] for call in calls], [1, 2])
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["folder"]["title"], "产品")

    def test_missing_cookie_requires_login_without_exposing_secret(self):
        with self.assertLogs("app.services.bilibili_favorites", level="INFO") as logs:
            with self.assertRaises(BilibiliFavoritesError) as raised:
                BilibiliFavoritesClient(cookie="", http_get=lambda *args, **kwargs: None).list_created_folders()

        self.assertEqual(raised.exception.code, "bilibili_login_required")
        self.assertNotIn("secret-session", str(raised.exception))
        self.assertNotIn("secret-session", "\n".join(logs.output))

    def test_rejected_cookie_maps_to_login_required_without_echoing_cookie(self):
        def fake_get(_url, *, params, headers, timeout):
            self.assertIn("SESSDATA=secret-session", headers["Cookie"])
            return {"code": -101, "message": "账号未登录"}

        with self.assertLogs("app.services.bilibili_favorites", level="WARNING") as logs:
            with self.assertRaises(BilibiliFavoritesError) as raised:
                BilibiliFavoritesClient(cookie=COOKIE, http_get=fake_get).list_created_folders()

        self.assertEqual(raised.exception.code, "bilibili_login_required")
        self.assertNotIn("secret-session", str(raised.exception))
        self.assertNotIn("secret-session", "\n".join(logs.output))

    def test_author_filter_uses_keyword_and_keeps_only_exact_upper(self):
        calls = []

        def fake_get(_url, *, params, headers, timeout):
            calls.append({"params": params, "headers": headers, "timeout": timeout})
            return {
                "code": 0,
                "data": {
                    "info": {"id": 1001, "title": "默认收藏夹", "media_count": 2705},
                    "medias": [
                        {
                            "id": 1,
                            "type": 2,
                            "bvid": "BV1",
                            "title": "目标视频",
                            "cover": "",
                            "duration": 10,
                            "upper": {"mid": 12345678, "name": "测试UP主"},
                            "pubtime": 1700000000,
                            "fav_time": 1,
                        },
                        {
                            "id": 2,
                            "type": 2,
                            "bvid": "BV2",
                            "title": "模糊匹配",
                            "cover": "",
                            "duration": 10,
                            "upper": {"mid": 9, "name": "测试UP主的粉丝"},
                            "fav_time": 2,
                        },
                    ],
                    "has_more": False,
                },
            }

        result = BilibiliFavoritesClient(
            cookie=COOKIE,
            http_get=fake_get,
        ).list_folder_videos(1001, author="测试UP主")

        self.assertEqual(calls[0]["params"]["keyword"], "测试UP主")
        self.assertEqual([video["bvid"] for video in result["videos"]], ["BV1"])
        self.assertEqual(result["videos"][0]["pub_time"], 1700000000)
        self.assertEqual(result["total"], 1)

    def test_lists_every_page_of_a_multi_part_video(self):
        def fake_get(url, *, params, headers, timeout):
            self.assertIn("web-interface/view", url)
            self.assertEqual(params, {"bvid": "BV1"})
            return {
                "code": 0,
                "data": {
                    "bvid": "BV1",
                    "title": "Python 合集",
                    "pages": [
                        {"page": 1, "part": "列表", "duration": 10, "cid": 101},
                        {"page": 2, "part": "元组", "duration": 20, "cid": 102},
                    ],
                },
            }

        result = BilibiliFavoritesClient(
            cookie=COOKIE,
            http_get=fake_get,
        ).list_video_pages("BV1")

        self.assertEqual(result["title"], "Python 合集")
        self.assertEqual([page["page"] for page in result["pages"]], [1, 2])
        self.assertEqual(result["pages"][1]["url"], "https://www.bilibili.com/video/BV1?p=2")


if __name__ == "__main__":
    unittest.main()
