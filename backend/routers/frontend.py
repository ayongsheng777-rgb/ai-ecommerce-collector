"""前台：登录后才能看。首页按 5 大模块展示，点进子分类看条目列表"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_login
from ..categories import load_categories, get_subcategory
from ..database import get_conn

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")

SOURCE_LABEL = {"github": "GitHub 自动采集", "rss": "新闻订阅自动采集", "manual": "人工整理录入"}


@router.get("/")
def index(request: Request):
    redir = require_login(request)
    if redir:
        return redir
    modules = load_categories()
    # 每个子分类算一条目数
    conn = get_conn()
    counts = {}
    for row in conn.execute("SELECT subcategory_id, COUNT(*) c FROM items GROUP BY subcategory_id"):
        counts[row["subcategory_id"]] = row["c"]
    conn.close()
    return templates.TemplateResponse(
        "frontend/index.html",
        {"request": request, "modules": modules, "counts": counts,
         "user": request.session.get("user"), "source_label": SOURCE_LABEL},
    )


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
        "SELECT * FROM items WHERE subcategory_id = ? ORDER BY stars DESC NULLS LAST, id DESC LIMIT 200",
        (sub_id,),
    ).fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return templates.TemplateResponse(
        "frontend/subcat.html",
        {"request": request, "sub": sub, "module": module, "items": items,
         "user": request.session.get("user"), "source_label": SOURCE_LABEL},
    )
