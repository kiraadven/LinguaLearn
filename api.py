"""
Compatibility entrypoint.

Root-level `python api.py` remains supported while the backend source
is organized under `backend/`.
"""

from backend.api import app

__all__ = ["app"]


if __name__ == "__main__":
    import os as _os
    import uvicorn

    _port = int(_os.getenv("PORT", 8080))
    print("🚀 LinguaLearn 服务启动中...")
    print(f"📱 打开浏览器访问: http://localhost:{_port}")
    uvicorn.run(app, host="0.0.0.0", port=_port, reload=False)

