#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import markdown as markdown_renderer


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bili_favorites import batch_status, item_output_id  # noqa: E402


STATUS_LABELS = {
    "SUCCESS": "全部成功",
    "PARTIAL": "部分成功",
    "FAILED": "失败",
    "IN_PROGRESS": "处理中",
}


def _markdown_html(value: str) -> str:
    return markdown_renderer.markdown(
        value,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


def _one_line(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip() == "一句话结论"
            continue
        if in_section and stripped:
            return stripped.lstrip("-* ").strip()
    return ""


def _section_text(markdown_text: str, heading: str) -> str:
    marker = f"## {heading}"
    lines = markdown_text.splitlines()
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == marker:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            collected.append(line)
    return "\n".join(collected).strip()


def _outline_tree(markdown_text: str, root_title: str) -> dict[str, Any]:
    root: dict[str, Any] = {"content": root_title, "children": []}
    current_section: dict[str, Any] | None = None
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = {
                "content": stripped[3:].strip(),
                "children": [],
            }
            root["children"].append(current_section)
        elif current_section is not None and stripped.startswith(("- ", "* ")):
            current_section["children"].append(
                {"content": stripped[2:].strip(), "children": []}
            )
    return root


def _outline_html(node: dict[str, Any]) -> str:
    children = node.get("children") or []
    nested = "".join(f"<li>{_outline_html(child)}</li>" for child in children)
    title = html.escape(str(node.get("content") or ""))
    if nested:
        return f"<strong>{title}</strong><ul>{nested}</ul>"
    return title


def _wrap_label(value: str, max_units: int = 28) -> list[str]:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_units and char in " ，。；：、,.!?！？;:":
            lines.append(current.strip())
            current = ""
        elif len(current) >= max_units + 8:
            lines.append(current.strip())
            current = ""
    if current.strip():
        lines.append(current.strip())
    return lines or [text]


def _static_mindmap_svg(tree: dict[str, Any]) -> str:
    groups: list[dict[str, Any]] = []
    top = 28
    for section in tree.get("children") or []:
        section_lines = _wrap_label(section.get("content") or "", 18)
        child_nodes = []
        for child in section.get("children") or []:
            lines = _wrap_label(child.get("content") or "", 34)
            child_nodes.append(
                {
                    "text": child.get("content") or "",
                    "lines": lines,
                    "height": max(40, len(lines) * 20 + 18),
                }
            )
        section_height = max(44, len(section_lines) * 20 + 18)
        children_height = sum(child["height"] for child in child_nodes)
        children_height += max(0, len(child_nodes) - 1) * 10
        group_height = max(section_height, children_height, 44)
        groups.append(
            {
                "section": section,
                "section_lines": section_lines,
                "section_height": section_height,
                "children": child_nodes,
                "group_height": group_height,
                "top": top,
            }
        )
        top += group_height + 22

    canvas_height = max(520, top + 20)
    root_lines = _wrap_label(tree.get("content") or "", 16)
    root_height = max(48, len(root_lines) * 20 + 20)
    root_x = 20
    root_y = canvas_height / 2 - root_height / 2
    section_x = 330
    section_width = 250
    child_x = 650
    child_width = 680
    canvas_width = 1370
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" class="static-mindmap" '
            f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" '
            f'aria-label="{html.escape(str(tree.get("content") or "思维导图"))}">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            "<style>"
            ".mm-root{fill:#0b6b4f;stroke:#07523d;stroke-width:2}"
            ".mm-section{fill:#e8f5ee;stroke:#19966d;stroke-width:1.5}"
            ".mm-child{fill:#fbfdfb;stroke:#9ab8a8;stroke-width:1}"
            ".mm-text{font-family:'Microsoft YaHei',Arial,sans-serif;fill:#17211b}"
            ".mm-root-text{font-family:'Microsoft YaHei',Arial,sans-serif;fill:white;font-weight:700}"
            ".mm-link{fill:none;stroke:#7fb59d;stroke-width:2}"
            "</style>"
        ),
    ]
    root_center = root_y + root_height / 2
    for index, group in enumerate(groups):
        section = group["section"]
        section_top = group["top"] + (group["group_height"] - group["section_height"]) / 2
        section_center = section_top + group["section_height"] / 2
        color_path = f'M{root_x + 250},{root_center} C290,{root_center} 290,{section_center} {section_x},{section_center}'
        parts.append(f'<path class="mm-link" d="{color_path}"/>')
        parts.append(
            f'<rect class="mm-section" x="{section_x}" y="{section_top:.1f}" '
            f'width="{section_width}" height="{group["section_height"]}" rx="14"/>'
        )
        for line_index, line in enumerate(group["section_lines"]):
            y = section_top + 26 + line_index * 20
            parts.append(
                f'<text class="mm-text" x="{section_x + 14}" y="{y:.1f}" '
                f'font-size="15" font-weight="700">{html.escape(line)}</text>'
            )

        child_y = group["top"] + (group["group_height"] - (
            sum(child["height"] for child in group["children"])
            + max(0, len(group["children"]) - 1) * 10
        )) / 2
        for child in group["children"]:
            child_center = child_y + child["height"] / 2
            path = (
                f'M{section_x + section_width},{section_center} '
                f'C590,{section_center} 590,{child_center} {child_x},{child_center}'
            )
            parts.append(f'<path class="mm-link" d="{path}"/>')
            parts.append(
                f'<rect class="mm-child" x="{child_x}" y="{child_y:.1f}" '
                f'width="{child_width}" height="{child["height"]}" rx="10"/>'
            )
            for line_index, line in enumerate(child["lines"]):
                y = child_y + 24 + line_index * 20
                parts.append(
                    f'<text class="mm-text" x="{child_x + 14}" y="{y:.1f}" '
                    f'font-size="14">{html.escape(line)}</text>'
                )
            child_y += child["height"] + 10

    parts.append(
        f'<rect class="mm-root" x="{root_x}" y="{root_y:.1f}" '
        f'width="250" height="{root_height}" rx="16"/>'
    )
    for line_index, line in enumerate(root_lines):
        y = root_y + 28 + line_index * 20
        parts.append(
            f'<text class="mm-root-text" x="{root_x + 16}" y="{y:.1f}" '
            f'font-size="16">{html.escape(line)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


CHAPTER_PATTERN = re.compile(
    r"^\s*-\s*\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.+?)\s*$"
)


def _format_time(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _chapter_payloads(
    markdown_text: str,
    transcript: dict[str, Any],
) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for line in markdown_text.splitlines():
        match = CHAPTER_PATTERN.match(line)
        if not match:
            continue
        first = int(match.group(1))
        second = int(match.group(2))
        third = match.group(3)
        start = (
            first * 3600 + second * 60 + int(third)
            if third is not None
            else first * 60 + second
        )
        chapters.append(
            {
                "start": start,
                "time": _format_time(start),
                "title": match.group(4).strip(),
            }
        )
    if not chapters:
        chapters = [{"start": 0, "time": "00:00", "title": "全文"}]

    segments = transcript.get("segments") or []
    for index, chapter in enumerate(chapters):
        end = chapters[index + 1]["start"] if index + 1 < len(chapters) else math.inf
        selected = []
        for segment in segments:
            start = float(segment.get("start") or 0)
            if chapter["start"] <= start < end:
                text = str(segment.get("text") or "").strip()
                if text:
                    selected.append(text)
        paragraphs = []
        for offset in range(0, len(selected), 8):
            paragraphs.append("".join(selected[offset:offset + 8]))
        chapter["text"] = "\n\n".join(paragraphs).strip()
        chapter["end"] = None if math.isinf(end) else int(end)
    return chapters


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return (cleaned or "章节")[:80]


def _chapter_transcript_html(
    chapters: list[dict[str, Any]],
    source_url: str,
) -> str:
    if not any(chapter.get("text") for chapter in chapters):
        return '<p class="muted">当前视频结果没有可用的逐句转写数据。</p>'
    sections = []
    for chapter in chapters:
        target = source_url
        if source_url:
            separator = "&" if "?" in source_url else "?"
            target = f"{source_url}{separator}t={chapter['start']}"
        link = (
            f'<a href="{html.escape(target)}" target="_blank" rel="noopener noreferrer">'
            "跳到视频位置</a>"
            if source_url
            else ""
        )
        paragraphs = "".join(
            f"<p>{html.escape(part)}</p>"
            for part in chapter["text"].split("\n\n")
            if part.strip()
        )
        sections.append(
            "<details>"
            f"<summary>[{chapter['time']}] {html.escape(chapter['title'])}</summary>"
            f"{link}{paragraphs or '<p class=\"muted\">该章节没有匹配到转写文本。</p>'}"
            "</details>"
        )
    return "".join(sections)


def _write_chapter_transcripts(
    destination: Path,
    title: str,
    chapters: list[dict[str, Any]],
    source_url: str,
) -> None:
    chapter_dir = destination.parent / "章节全文"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    combined = [f"# {title} - 章节全文", ""]
    if source_url:
        combined.extend([f"> 原视频：{source_url}", ""])
    for index, chapter in enumerate(chapters, 1):
        heading = f"[{chapter['time']}] {chapter['title']}"
        target = source_url
        if source_url:
            separator = "&" if "?" in source_url else "?"
            target = f"{source_url}{separator}t={chapter['start']}"
        body = chapter["text"] or "（该章节没有匹配到转写文本。）"
        single = [f"# {heading}", "", f"> 原视频：{target}" if target else "", "", body, ""]
        file_name = f"{index:03d}-{_safe_filename(chapter['title'])}.md"
        (chapter_dir / file_name).write_text("\n".join(single), encoding="utf-8")
        combined.extend(
            [
                f"## {heading}",
                "",
                f"[跳到视频位置]({target})" if target else "",
                "",
                body,
                "",
            ]
        )
    (destination.parent / "章节全文.md").write_text(
        "\n".join(combined),
        encoding="utf-8",
    )


def _page(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17211b; --muted:#667067; --line:#dbe4dc; --accent:#087f5b; --soft:#f3f8f4; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:#f7f9f7; color:var(--ink); font:16px/1.75 system-ui,-apple-system,"Microsoft YaHei",sans-serif; }}
    main {{ width:min(1040px, calc(100% - 28px)); margin:28px auto 64px; }}
    .hero,.panel {{ background:white; border:1px solid var(--line); border-radius:18px; padding:24px; box-shadow:0 8px 28px rgba(20,50,30,.05); }}
    .hero {{ margin-bottom:18px; }}
    .eyebrow {{ color:var(--accent); font-weight:700; font-size:13px; letter-spacing:.08em; }}
    h1 {{ margin:.25em 0; line-height:1.25; font-size:clamp(24px,4vw,40px); }}
    h2 {{ margin-top:1.6em; border-top:1px solid var(--line); padding-top:1.1em; }}
    h3 {{ margin-top:1.2em; }}
    a {{ color:var(--accent); text-decoration-thickness:1.5px; text-underline-offset:3px; }}
    .muted {{ color:var(--muted); }}
    .panel {{ margin-top:18px; }}
    .stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
    .stat {{ background:var(--soft); border-radius:999px; padding:5px 12px; }}
    .failure {{ color:#b42318; }}
    table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
    th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:9px 8px; vertical-align:top; }}
    #mindmap {{ width:100%; height:560px; border:1px solid var(--line); border-radius:12px; background:white; }}
    .mindmap-static {{ width:100%; overflow:auto; border:1px solid var(--line); border-radius:12px; background:white; }}
    .mindmap-static svg {{ display:block; width:100%; min-width:980px; height:auto; }}
    .chapter-full p {{ margin:.65em 0; }}
    details {{ margin-top:14px; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
    @media print {{ body {{ background:white; }} main {{ width:100%; margin:0; }} .hero,.panel {{ box-shadow:none; break-inside:avoid; }} #mindmap {{ display:none; }} }}
  </style>
  {extra_head}
</head>
<body><main>{body}</main></body>
</html>
"""


def render_video_card(
    result: dict[str, Any],
    destination: Path,
    *,
    source_url: str = "",
) -> None:
    markdown_text = str(result.get("markdown") or "")
    audio_meta = result.get("audio_meta") or {}
    title = str(audio_meta.get("title") or "B 站视频知识卡")
    tree = _outline_tree(markdown_text, title)
    tree_json = json.dumps(tree, ensure_ascii=False).replace("<", "\\u003c")
    static_svg = _static_mindmap_svg(tree)
    transcript = result.get("transcript") or {}
    chapters = _chapter_payloads(markdown_text, transcript)
    source_link = (
        f'<p><a href="{html.escape(source_url)}" target="_blank" rel="noopener noreferrer">'
        "打开原视频</a></p>"
        if source_url
        else ""
    )
    body = f"""
<article class="hero">
  <p class="eyebrow">BiliBrief 知识卡</p>
  <h1>{html.escape(title)}</h1>
  {source_link}
</article>
<section class="panel">
  <h2 style="margin-top:0;border-top:0;padding-top:0">思维导图</h2>
  <div class="mindmap-static">{static_svg}</div>
  <details>
    <summary>交互版思维导图</summary>
    <svg id="mindmap" aria-label="视频知识交互思维导图"></svg>
  </details>
  <details>
    <summary>文字版思维导图</summary>
    <ul>{_outline_html(tree)}</ul>
  </details>
</section>
<article class="panel">{_markdown_html(markdown_text)}</article>
<section class="panel chapter-full">
  <h2 style="margin-top:0;border-top:0;padding-top:0">章节全文</h2>
  <p class="muted">全文同时已导出到“章节全文.md”和“章节全文”目录。</p>
  {_chapter_transcript_html(chapters, source_url)}
</section>
<script type="application/json" id="mindmap-data">{tree_json}</script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/markmap-view@0.18.10"></script>
<script>
  (() => {{
    const data = JSON.parse(document.getElementById('mindmap-data').textContent);
    const target = document.getElementById('mindmap');
    if (!window.markmap || !target) return;
    const mm = window.markmap.Markmap.create(target);
    mm.setData(data).then(() => mm.fit());
  }})();
</script>
"""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (destination.parent / "思维导图.svg").write_text(static_svg, encoding="utf-8")
    _write_chapter_transcripts(destination, title, chapters, source_url)
    destination.write_text(_page(title, body), encoding="utf-8")


def render_batch_report(manifest: dict[str, Any], destination: Path) -> None:
    destination = Path(destination)
    batch_dir = destination.parent
    report_markdown_path = batch_dir / "总报告.md"
    existing_analysis = ""
    if report_markdown_path.is_file():
        existing_analysis = _section_text(
            report_markdown_path.read_text(encoding="utf-8"),
            "跨视频分析",
        )
    items = manifest.get("items", [])
    successful = [item for item in items if item.get("state") == "success"]
    failed = [item for item in items if item.get("state") == "failed"]
    skipped = [item for item in items if item.get("state") == "skipped"]
    status = batch_status(items)
    folder_title = str((manifest.get("folder") or {}).get("title") or "B 站收藏夹")

    success_rows = []
    success_markdown = []
    for item in successful:
        bvid = str(item.get("bvid") or "")
        output_id = item_output_id(item)
        result_path = batch_dir / "videos" / output_id / "result.json"
        one_line = ""
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            one_line = _one_line(str(result.get("markdown") or ""))
        title = str(item.get("title") or bvid)
        success_rows.append(
            "<tr>"
            f"<td><a href=\"videos/{html.escape(output_id)}/知识卡.html\">{html.escape(title)}</a></td>"
            f"<td>{html.escape(one_line or '未提取到一句话结论')}</td>"
            "</tr>"
        )
        success_markdown.append(
            f"- [{title}](videos/{output_id}/摘要.md)"
            + (f" — {one_line}" if one_line else "")
        )

    failure_html = "".join(
        "<li>"
        f"<strong>{html.escape(str(item.get('title') or item.get('bvid') or '未命名'))}</strong>"
        f"：{html.escape(str(item.get('message') or '任务失败'))}"
        "</li>"
        for item in failed
    )
    skipped_html = "".join(
        "<li>"
        f"<strong>{html.escape(str(item.get('title') or '未命名'))}</strong>"
        f"：{html.escape(str(item.get('message') or '已跳过'))}"
        "</li>"
        for item in skipped
    )
    body = f"""
<section class="hero">
  <p class="eyebrow">BiliBrief 收藏夹总报告</p>
  <h1>{html.escape(folder_title)}</h1>
  <p class="muted">批次状态：{html.escape(STATUS_LABELS.get(status, status))}</p>
  <div class="stats">
    <span class="stat">成功 {len(successful)}</span>
    <span class="stat failure">失败 {len(failed)}</span>
    <span class="stat">跳过 {len(skipped)}</span>
  </div>
</section>
<section class="panel">
  <h2 style="margin-top:0;border-top:0;padding-top:0">成功视频</h2>
  <table><thead><tr><th>视频标题</th><th>一句话结论</th></tr></thead>
  <tbody>{''.join(success_rows) or '<tr><td colspan="2">没有成功视频</td></tr>'}</tbody></table>
</section>
<section class="panel failure">
  <h2 style="margin-top:0;border-top:0;padding-top:0">失败项</h2>
  <ul>{failure_html or '<li>无</li>'}</ul>
</section>
<section class="panel">
  <h2 style="margin-top:0;border-top:0;padding-top:0">已跳过</h2>
  <ul>{skipped_html or '<li>无</li>'}</ul>
</section>
<section class="panel">
  <h2 style="margin-top:0;border-top:0;padding-top:0">跨视频分析</h2>
  {_markdown_html(existing_analysis) if existing_analysis else '<p class="muted">请让 Codex/WorkBuddy 根据各视频摘要补充共同主题、观看顺序和行动建议，然后重新渲染。</p>'}
</section>
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_page(f"{folder_title} - 知识卡总报告", body), encoding="utf-8")

    failure_lines = [
        f"- {item.get('title') or item.get('bvid') or '未命名'}：{item.get('message') or '任务失败'}"
        for item in failed
    ]
    skipped_lines = [
        f"- {item.get('title') or '未命名'}：{item.get('message') or '已跳过'}"
        for item in skipped
    ]
    markdown_text = "\n".join(
        [
            f"# {folder_title} 收藏夹知识卡报告",
            "",
            f"- 批次状态：{STATUS_LABELS.get(status, status)}",
            f"- 成功：{len(successful)}",
            f"- 失败：{len(failed)}",
            f"- 跳过：{len(skipped)}",
            "",
            "## 成功视频",
            "",
            *(success_markdown or ["- 无"]),
            "",
            "## 失败项",
            "",
            *(failure_lines or ["- 无"]),
            "",
            "## 已跳过",
            "",
            *(skipped_lines or ["- 无"]),
            "",
            "## 跨视频分析",
            "",
            existing_analysis or "<!-- 由 Codex/WorkBuddy 根据各视频摘要补充。 -->",
            "",
        ]
    )
    report_markdown_path.write_text(markdown_text, encoding="utf-8")
