from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.transcriber_config_manager import TranscriberConfigManager
from app.utils.response import ResponseWrapper as R

router = APIRouter(prefix="/asr", tags=["BiliBrief ASR"])

AsrMode = Literal["subtitle_only", "bcut", "kuaishou", "groq"]

MODE_TO_TRANSCRIBER = {
    "subtitle_only": "subtitle_only",
    "bcut": "bcut",
    "kuaishou": "kuaishou",
    "groq": "groq",
}


class AsrSettingsRequest(BaseModel):
    mode: AsrMode


def _to_mode(transcriber_type: str) -> str:
    return (
        transcriber_type
        if transcriber_type in MODE_TO_TRANSCRIBER
        else "subtitle_only"
    )


def _settings_payload(config: dict) -> dict:
    return {
        "mode": _to_mode(str(config.get("transcriber_type") or "")),
        "available_modes": list(MODE_TO_TRANSCRIBER),
    }


@router.get("/settings")
def get_asr_settings():
    try:
        config = TranscriberConfigManager().get_config()
        return R.success(data=_settings_payload(config))
    except Exception as exc:
        return R.error(msg=f"读取 ASR 设置失败：{exc}")


@router.put("/settings")
def update_asr_settings(data: AsrSettingsRequest):
    try:
        config = TranscriberConfigManager().update_brief_mode(
            MODE_TO_TRANSCRIBER[data.mode],
        )
        return R.success(data=_settings_payload(config))
    except Exception as exc:
        return R.error(msg=f"保存 ASR 设置失败：{exc}")
