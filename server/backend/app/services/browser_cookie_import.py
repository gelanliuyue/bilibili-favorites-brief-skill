from __future__ import annotations

from typing import Callable, Literal

from app.services.cookie_manager import CookieConfigManager

SupportedBrowser = Literal["edge", "chrome"]


def import_bilibili_cookies(
    browser: SupportedBrowser,
    *,
    extractor: Callable[[str], object] | None = None,
    cookie_manager: CookieConfigManager | None = None,
) -> str:
    if browser not in {"edge", "chrome"}:
        raise ValueError("Only edge and chrome browser cookie import is supported")

    if extractor is None:
        from yt_dlp.cookies import extract_cookies_from_browser

        extractor = extract_cookies_from_browser

    try:
        jar = extractor(browser)
    except Exception as exc:
        raise ValueError(
            f"Unable to read {browser} cookies. Close the browser if its cookie database is locked."
        ) from exc

    values: dict[str, str] = {}
    for cookie in jar:
        domain = str(getattr(cookie, "domain", "")).lower()
        name = str(getattr(cookie, "name", "")).strip()
        value = getattr(cookie, "value", None)
        if domain.endswith("bilibili.com") and name and value is not None:
            safe_value = str(value).replace("\r", "").replace("\n", "")
            values[name] = safe_value

    if not values.get("SESSDATA"):
        raise ValueError("The selected browser does not contain a Bilibili SESSDATA cookie")

    ordered_names = (
        "SESSDATA",
        "bili_jct",
        "DedeUserID",
        "DedeUserID__ckMd5",
        "sid",
    )
    ordered = [
        (name, values.pop(name))
        for name in ordered_names
        if name in values
    ]
    ordered.extend(values.items())
    cookie_header = "; ".join(f"{name}={value}" for name, value in ordered)

    (cookie_manager or CookieConfigManager()).set("bilibili", cookie_header)
    return cookie_header
