"""登录/退出"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import get_user, check_password

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@router.post("/login")
def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user(username.strip())
    if user and check_password(password, user["password_hash"]):
        request.session["user"] = {
            "username": user["username"],
            "is_admin": bool(user["is_admin"]),
        }
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "账号或密码不对，请再试一次"}, status_code=401
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
