"""前台：登录后才能看。
首页：欢迎横幅 + 3 大模块统计卡片 + 全站最新 12 条。
模块页 /m/{module_id}：该模块下每个子分类一张卡片，各列前 5 条。
子分类页 /c/{sub_id}：完整列表，英文源双语展示，GitHub 显示星数。
搜索 /search?q=：按关键词搜标题和简介（含中文译文）。"""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_login
from ..categories import load_categories, get_subcategory
from ..database import get_conn

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")

SOURCE_LABEL = {
    "github": "GitHub 自动采集",
    "rss": "新闻订阅自动采集",
    "rss_en": "海外英文资讯（自动翻译）",
    "manual": "人工整理录入",
}

ITEM_ORDER = "ORDER BY stars DESC NULLS LAST, id DESC"


def _ctx(request, **kw):
    user = request.session.get("user")
    modules = load_categories()
    kw.update({"request": request, "modules": modules, "user": user,
               "source_label": SOURCE_LABEL})
    return kw


def _counts(conn):
    counts = {}
    for row in conn.execute("SELECT subcategory_id, COUNT(*) c FROM items GROUP BY subcategory_id"):
        counts[row["subcategory_id"]] = row["c"]
    return counts


@router.get("/")
def index(request: Request):
    redir = require_login(request)
    if redir:
        return redir
    conn = get_conn()
    counts = _counts(conn)
    # 今日更新条数：collected_at 是今天的
    today = conn.execute(
        "SELECT COUNT(*) c FROM items WHERE substr(collected_at, 1, 10) = date('now', 'localtime')"
    ).fetchone()["c"]
    # 全站最新 12 条
    latest = [dict(r) for r in conn.execute(
        "SELECT * FROM items ORDER BY collected_at DESC, id DESC LIMIT 12")]
    conn.close()
    modules = load_categories()
    module_counts = {m["id"]: sum(counts.get(s["id"], 0) for s in m.get("subcategories", []))
                     for m in modules}
    today_str = datetime.now().strftime("%Y年%m月%d日")
    return templates.TemplateResponse("frontend/index.html", _ctx(
        request, counts=counts, today_count=today, today=today_str,
        module_counts=module_counts, latest=latest, active="home"))


@router.get("/m/{module_id}")
def module_page(request: Request, module_id: str):
    redir = require_login(request)
    if redir:
        return redir
    modules = load_categories()
    module = next((m for m in modules if m["id"] == module_id), None)
    if not module:
        return RedirectResponse(url="/", status_code=302)
    conn = get_conn()
    counts = _counts(conn)
    previews = {}
    for sub in module.get("subcategories", []):
        rows = conn.execute(
            f"SELECT * FROM items WHERE subcategory_id = ? {ITEM_ORDER} LIMIT 5",
            (sub["id"],),
        ).fetchall()
        previews[sub["id"]] = [dict(r) for r in rows]
    conn.close()
    return templates.TemplateResponse("frontend/module.html", _ctx(
        request, module=module, counts=counts, previews=previews, active=module_id))


@router.get("/c/{sub_id}")
def subcat_page(request: Request, sub_id: str):
    redir = require_login(request)
    if redir:
        return redir
    sub, module = get_subcategory(sub_id)
    if not sub:
        return RedirectResponse(url="/", status_code=302)
    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM items WHERE subcategory_id = ? {ITEM_ORDER} LIMIT 200",
        (sub_id,),
    ).fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return templates.TemplateResponse("frontend/subcat.html", _ctx(
        request, sub=sub, module=module, items=items, active=module["id"]))


@router.get("/search")
def search(request: Request, q: str = ""):
    redir = require_login(request)
    if redir:
        return redir
    q = q.strip()
    items = []
    if q:
        conn = get_conn()
        like = f"%{q}%"
        rows = conn.execute(
            "SELECT * FROM items WHERE title LIKE ? OR title_cn LIKE ? "
            "OR description LIKE ? OR summary_cn LIKE ? "
            "ORDER BY collected_at DESC, id DESC LIMIT 100",
            (like, like, like, like),
        ).fetchall()
        conn.close()
        items = [dict(r) for r in rows]
    return templates.TemplateResponse("frontend/search.html", _ctx(
        request, q=q, items=items, active=""))
