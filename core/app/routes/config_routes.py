"""User config and segments routes."""

from datetime import datetime
import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse


def build_config_router(
    *,
    database,
    require_user: Callable,
    get_job_or_404: Callable,
    output_dir: Path,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/config/save")
    async def save_config(
        config_json: str = Form(...),
        current_user: dict = Depends(require_user),
    ):
        """保存用户配置"""
        try:
            json.loads(config_json)
        except Exception:
            raise HTTPException(400, "配置 JSON 格式不正确")

        if database.save_user_config(current_user["email"], config_json):
            return {"status": "ok"}
        raise HTTPException(500, "保存配置失败")

    @router.get("/api/config/load")
    async def load_config(current_user: dict = Depends(require_user)):
        """加载用户配置"""
        cfg = database.get_user_config(current_user["email"])
        if cfg:
            return {"config": cfg}
        return {"config": None}

    @router.post("/api/config/presets")
    async def create_config_preset(
        name: str = Form(...),
        config_json: str = Form(...),
        current_user: dict = Depends(require_user),
    ):
        """保存命名配置预设"""
        try:
            json.loads(config_json)
        except Exception:
            raise HTTPException(400, "配置 JSON 格式不正确")
        name = name.strip() or f"配置 {datetime.now().strftime('%m-%d %H:%M')}"
        preset_id = database.save_config_preset(current_user["email"], name, config_json)
        if preset_id < 0:
            raise HTTPException(500, "保存预设失败")
        return {"id": preset_id, "name": name, "created_at": datetime.now().isoformat()}

    @router.get("/api/config/presets")
    async def list_config_presets(current_user: dict = Depends(require_user)):
        """列出用户所有命名配置预设"""
        presets = database.get_config_presets(current_user["email"])
        return {"presets": presets}

    @router.delete("/api/config/presets/{preset_id}")
    async def delete_config_preset(preset_id: int, current_user: dict = Depends(require_user)):
        """删除命名配置预设"""
        ok = database.delete_config_preset(preset_id, current_user["email"])
        if not ok:
            raise HTTPException(404, "预设不存在")
        return {"status": "ok"}

    @router.get("/api/jobs/{job_id}/segments")
    async def get_job_segments(job_id: str):
        """获取视频的句子时间戳（供视频预览页同步文稿使用）"""
        get_job_or_404(job_id)
        path = output_dir / job_id / "segments.json"
        if not path.exists():
            return JSONResponse(content=[], headers={"Cache-Control": "no-store"})
        data = json.loads(path.read_text(encoding="utf-8"))
        return JSONResponse(content=data, headers={"Cache-Control": "no-store"})

    return router

