from fastapi import Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import time
import secrets

from .database import get_db
from .auth import authenticate_user
from .app_context import templates
from Security.audit_trail import audit



def _redirect_for_role(role: str) -> str:
    if role == "admin":
        return "/admin/select_dashboard"
    if role == "manager":
        return "/manager/manage_teams"
    if role == "team_lead":
        return "/leader/dashboard"
    return "/employee"


def register_web_auth_routes(app):
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        logged_out = str(request.query_params.get("logged_out") or "").strip().lower() in {"1", "true", "yes"}
        return templates.TemplateResponse("auth/login.html", {"request": request, "logged_out": logged_out})

    @app.get("/401", response_class=HTMLResponse)
    async def unauthorized_page(request: Request):
        return templates.TemplateResponse("auth/401.html", {"request": request}, status_code=401)

    @app.post("/login")
    async def login_submit(
        request: Request,
        db: Session = Depends(get_db)
    ):
        form = await request.form()
        input_username = str(form.get("username") or "").strip()
        input_password = str(form.get("password") or "")
        if not input_username or not input_password:
            return templates.TemplateResponse(
                "auth/login.html",
                {"request": request, "error": "Employee ID and password are required", "username_value": input_username},
                status_code=400
            )
        user = authenticate_user(db, input_username, input_password)

        if not user:
            audit("auth_login_failed", user_id=None, details=f"employee_id={input_username}")
            return templates.TemplateResponse(
                "auth/login.html",
                {"request": request, "error": "Invalid credentials", "username_value": input_username},
                status_code=401
            )

        if not user.is_active:
            audit("auth_login_inactive", user_id=user.id, details=f"employee_id={user.employee_id}")
            raise HTTPException(status_code=403, detail="Account is inactive")

        new_session_id = secrets.token_urlsafe(32)

        request.session["user_id"] = user.id
        request.session["role"] = user.role
        request.session["session_id"] = new_session_id
        request.session["_created"] = int(time.time())
        request.session["_last_seen"] = int(time.time())
        audit("auth_login_success", user_id=user.id, details=f"employee_id={user.employee_id};role={user.role}")
        response = RedirectResponse(_redirect_for_role(user.role), status_code=303)
        response.delete_cookie("ts_logged_out", path="/")
        return response

    @app.get("/logout")
    async def logout(request: Request):
        existing_user_id = request.session.get("user_id")
        if not existing_user_id:
            return RedirectResponse("/401", status_code=303)
        audit("auth_logout", user_id=existing_user_id, details="logout")
        request.session.clear()
        response = RedirectResponse("/login?logged_out=1", status_code=303)
        response.set_cookie(
            "ts_logged_out",
            "1",
            max_age=300,
            path="/",
            httponly=False,
            samesite="lax",
        )
        return response

