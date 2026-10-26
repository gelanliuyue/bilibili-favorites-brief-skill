from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable


@dataclass
class PreflightResult:
    transcript: dict[str, Any] | None = None
    blocking_reason: dict[str, Any] | None = None


def resolve_brief_transcript(
    *,
    prefetched_transcript: dict[str, Any] | None,
    readiness: dict[str, Any],
    fetch_subtitles: Callable[[str], Any],
    video_url: str,
) -> PreflightResult:
    """Resolve a transcript before enforcing the local transcriber gate."""
    if prefetched_transcript:
        return PreflightResult(transcript=prefetched_transcript)

    if readiness.get("ready"):
        return PreflightResult()

    try:
        transcript = fetch_subtitles(video_url)
    except Exception:
        transcript = None
    if transcript is not None:
        payload = asdict(transcript) if is_dataclass(transcript) else transcript
        if isinstance(payload, dict) and payload.get("segments"):
            return PreflightResult(transcript=payload)

    return PreflightResult(
        blocking_reason={
            "reason": "transcriber_model_not_ready",
            "transcriber_type": readiness.get("transcriber_type"),
            "model_size": readiness.get("model_size"),
            "downloading": bool(readiness.get("downloading")),
            "message": readiness.get("reason") or "转写模型尚未就绪",
            "subtitle_checked": True,
        }
    )
