"""登录与权限：密码用 bcrypt 加密存放，登录成功后在 session 里记用户信息"""
import os
import bcrypt
from datetime import datetime
from fastapi import Request
from fastapi.responses import RedirectResponse
from .database import get_conn


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_user(username: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_current_user(request: Request):
    return request.session.get("user")


def require_login(request: Request):
    """前台：没登录就跳到登录页"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return None


def require_admin(request: Request):
    """后台：必须是管理员"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not user.get("is_admin"):
        return RedirectResponse(url="/", status_code=302)
    return None


def ensure_admin_user():
    """容器首次启动时，用环境变量创建初始管理员账号"""
    username = os.environ.get("ADMIN_USER", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        print("[警告] 没有设置 ADMIN_PASSWORD 环境变量，初始管理员账号未创建，请在 .env 里配置后再重启。")
        return
    conn = get_conn()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
            (username, hash_password(password), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        print(f"[启动] 已创建初始管理员账号：{username}")
    conn.close()
