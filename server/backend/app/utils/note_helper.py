import re


def prepend_source_link(markdown: str | None, source_url: str) -> str | None:
    """
    在笔记开头添加来源链接；若首个非空行已包含来源链接，则更新该行并避免重复。
    """
    if markdown is None:
        return None

    source = (source_url or "").strip()
    if not source:
        return markdown

    header = f"> 来源链接：{source}"
    lines = markdown.splitlines()
    first_non_empty_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_idx = idx
            break

    if first_non_empty_idx is not None:
        first_line = lines[first_non_empty_idx].strip()
        if first_line.startswith("> 来源链接：") or first_line.startswith("来源链接："):
            lines[first_non_empty_idx] = header
            return "\n".join(lines)

    if markdown.strip():
        return f"{header}\n\n{markdown}"
    return header


def replace_content_markers(markdown: str, video_id: str, platform: str = 'bilibili') -> str:
    """
    替换 *Content-04:16*、Content-04:16 或 Content-[04:16] 为超链接，跳转到对应平台视频的时间位置
    """
    # 匹配三种形式：*Content-04:16*、Content-04:16、Content-[04:16]
    pattern = r"(?:\*?)Content-(?:\[(\d{2}):(\d{2})\]|(\d{2}):(\d{2}))"

    safe_video_id = video_id

    def replacer(match):
        mm = match.group(1) or match.group(3)
        ss = match.group(2) or match.group(4)
        total_seconds = int(mm) * 60 + int(ss)

        if platform == 'bilibili':
            video_id = video_id.replace("_p", "?p=")
            url = f"https://www.bilibili.com/video/{video_id}&t={total_seconds}"
            parsed_video_id = safe_video_id.replace("_p", "?p=")
            url = f"https://www.bilibili.com/video/{parsed_video_id}&t={total_seconds}"
        elif platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}&t={total_seconds}s"
            url = f"https://www.youtube.com/watch?v={safe_video_id}&t={total_seconds}s"
        elif platform == 'douyin':
            url = f"https://www.douyin.com/video/{video_id}"
            url = f"https://www.douyin.com/video/{safe_video_id}"
            return f"[原片 @ {mm}:{ss}]({url})"
        else:
            return f"({mm}:{ss})"

        return f"[原片 @ {mm}:{ss}]({url})"

    return re.sub(pattern, replacer, markdown)


# 匹配简介里出现的 http/https 链接，遇到空白、引号、括号或中文标点即停止
_URL_PATTERN = re.compile(r"https?://[^\s<>\"'）)】\]】，。；、]+")
# 链接末尾常见的英文标点，属于句子而不是 URL
_URL_TRAILING = ".,;:!?)]}>\"'"


def extract_urls(text: str, limit: int = 10) -> list[str]:
    """
    从简介文本中按出现顺序抽取 URL 并去重。

    只做字符串截取，不改写 URL 任何部分，保证 GitHub / 网盘等链接原样可用。
    """
    if not text:
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for raw in _URL_PATTERN.findall(str(text)):
        url = raw.rstrip(_URL_TRAILING)
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def append_related_links(
    markdown: str | None,
    description: str | None,
    limit: int = 10,
    heading: str = "## 相关链接",
) -> str | None:
    """
    把简介里的链接以「相关链接」小节追加到笔记末尾。

    链接由代码直接写入而非常让模型复述，避免模型改写 URL 导致链接失效；
    用 `<url>` 自动链接语法包裹，既保证可点击，也不受 Markdown 特殊字符影响。
    """
    if markdown is None:
        return None

    urls = extract_urls(description, limit=limit)
    if not urls:
        return markdown

    if heading in markdown:
        # 已存在同名小节时不重复追加，避免历史笔记被叠加
        return markdown

    section = "\n".join(f"- <{url}>" for url in urls)
    body = f"{heading}\n\n{section}\n"
    stripped = markdown.rstrip()
    return f"{stripped}\n\n{body}" if stripped else body

