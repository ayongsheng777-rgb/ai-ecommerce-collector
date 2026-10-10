"""后台管理：只有管理员能进。
功能：手动触发采集、增删改条目、启停子分类、管理账号、改自己的密码、看采集日志"""
import threading
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_admin, hash_password, check_password, get_user
from ..categories import load_categories, set_subcat_enabled
from ..database import get_conn
from ..collectors.scheduler import run_full_collect

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="backend/templates")

_collecting = False


def _tpl(name, request, **kw):
    kw.update({"request": request, "user": request.session.get("user")})
    return templates.TemplateResponse(name, kw)


@router.get("")
def dashboard(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    logs = conn.execute("SELECT * FROM collect_logs ORDER BY id DESC LIMIT 20").fetchall()
    stats = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
    conn.close()
    return _tpl("admin/dashboard.html", request, logs=[dict(r) for r in logs],
                total_items=stats, collecting=_collecting)


@router.post("/collect")
def trigger_collect(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    global _collecting
    if _collecting:
        return RedirectResponse(url="/admin?msg=collecting", status_code=302)
    _collecting = True

    def _run():
        global _collecting
        try:
            run_full_collect()
        finally:
            _collecting = False

    threading.Thread(target=_run, daemon=True).start()
    return RedirectResponse(url="/admin?msg=started", status_code=302)


# ---------- 条目管理 ----------
@router.get("/items")
def items_list(request: Request, sub: str = ""):
    redir = require_admin(request)
    if redir:
        return redir
    modules = load_categories()
    conn = get_conn()
    if sub:
        rows = conn.execute("SELECT * FROM items WHERE subcategory_id = ? ORDER BY id DESC LIMIT 200", (sub,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM items WHERE is_manual = 1 ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    return _tpl("admin/items.html", request, modules=modules, items=[dict(r) for r in rows], cur_sub=sub)


@router.get("/items/new")
def item_new(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    return _tpl("admin/item_form.html", request, modules=load_categories(), item=None)


@router.post("/items/new")
def item_create(request: Request, subcategory_id: str = Form(...), title: str = Form(...),
                url: str = Form(...), description: str = Form(""), source_name: str = Form("")):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    conn.execute(
        """INSERT INTO items (subcategory_id, title, url, description, source_name,
                              collected_at, is_manual)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (subcategory_id, title.strip(), url.strip(), description.strip()[:300],
         source_name.strip() or "人工录入", datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/items?sub={subcategory_id}", status_code=302)


@router.get("/items/{item_id}/edit")
def item_edit(request: Request, item_id: int):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not row:
        return RedirectResponse(url="/admin/items", status_code=302)
    return _tpl("admin/item_form.html", request, modules=load_categories(), item=dict(row))


@router.post("/items/{item_id}/edit")
def item_update(request: Request, item_id: int, subcategory_id: str = Form(...),
                title: str = Form(...), url: str = Form(...),
                description: str = Form(""), source_name: str = Form("")):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    conn.execute(
        "UPDATE items SET subcategory_id=?, title=?, url=?, description=?, source_name=? WHERE id=?",
        (subcategory_id, title.strip(), url.strip(), description.strip()[:300],
         source_name.strip() or "人工录入", item_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/items?sub={subcategory_id}", status_code=302)


@router.post("/items/{item_id}/delete")
def item_delete(request: Request, item_id: int):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/items", status_code=302)


# ---------- 分类启停 ----------
@router.get("/categories")
def categories_page(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    return _tpl("admin/categories.html", request, modules=load_categories())


@router.post("/categories/toggle")
def categories_toggle(request: Request, sub_id: str = Form(...), enabled: str = Form("0")):
    redir = require_admin(request)
    if redir:
        return redir
    set_subcat_enabled(sub_id, enabled == "1")
    return RedirectResponse(url="/admin/categories", status_code=302)


# ---------- 账号管理 ----------
@router.get("/users")
def users_page(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    rows = conn.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return _tpl("admin/users.html", request, users=[dict(r) for r in rows])


@router.post("/users/new")
def user_create(request: Request, username: str = Form(...), password: str = Form(...),
                is_admin: str = Form("0")):
    redir = require_admin(request)
    if redir:
        return redir
    username = username.strip()
    if not username or not password or get_user(username):
        return RedirectResponse(url="/admin/users?msg=bad", status_code=302)
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
        (username, hash_password(password), 1 if is_admin == "1" else 0,
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{uid}/reset")
def user_reset(request: Request, uid: int, password: str = Form(...)):
    """重置某个账号的密码"""
    redir = require_admin(request)
    if redir:
        return redir
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (hash_password(password), uid))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/users?msg=reset", status_code=302)


@router.post("/users/{uid}/delete")
def user_delete(request: Request, uid: int):
    redir = require_admin(request)
    if redir:
        return redir
    me = request.session.get("user", {}).get("username")
    conn = get_conn()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (uid,)).fetchone()
    # 不能删自己
    if row and row["username"] != me:
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/password")
def password_page(request: Request):
    redir = require_admin(request)
    if redir:
        return redir
    return _tpl("admin/password.html", request, msg=request.query_params.get("msg", ""))


@router.post("/password")
def password_change(request: Request, old: str = Form(...), new: str = Form(...)):
    redir = require_admin(request)
    if redir:
        return redir
    me = request.session.get("user", {}).get("username")
    user = get_user(me)
    if not user or not check_password(old, user["password_hash"]) or len(new) < 4:
        return RedirectResponse(url="/admin/password?msg=bad", status_code=302)
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                 (hash_password(new), me))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/password?msg=ok", status_code=302)
