"""程序入口：挂路由、建表、建初始管理员、启动每天凌晨 3 点的自动采集"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .models import init_db
from .auth import ensure_admin_user
from .collectors.scheduler import start_scheduler
from .routers import auth as auth_router, frontend as frontend_router, admin as admin_router

app = FastAPI(title="AI 与电商数据采集")

SECRET = os.environ.get("SESSION_SECRET", "")
if not SECRET:
    import secrets
    SECRET = secrets.token_hex(32)
    print("[提醒] 未设置 SESSION_SECRET，已随机生成；重启后登录会失效，正式用请在 .env 里固定一个。")

app.add_middleware(SessionMiddleware, secret_key=SECRET, max_age=7 * 24 * 3600)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

app.include_router(auth_router.router)
app.include_router(frontend_router.router)
app.include_router(admin_router.router)


@app.on_event("startup")
def on_startup():
    init_db()
    ensure_admin_user()
    start_scheduler()


@app.get("/health")
def health():
    return {"ok": True}
