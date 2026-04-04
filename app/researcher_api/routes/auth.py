from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.researcher_api.auth import SESSION_COOKIE_NAME, issue_session_token, require_researcher_auth

router = APIRouter(prefix="/admin/api/v1/auth", tags=["admin-auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login")
def login(req: LoginRequest, request: Request, response: Response) -> dict:
    user = request.app.state.auth_service.authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = issue_session_token(user, request.app.state.researcher_session_secret)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=bool(getattr(request.app.state, "researcher_cookie_secure", False)),
        max_age=60 * 60 * 12,
    )
    return {"ok": True, "user": {"user_id": user.user_id, "username": user.username, "is_admin": user.is_admin}}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def current_user(request: Request) -> dict:
    user = require_researcher_auth(request)
    return {"authenticated": True, "user": {"user_id": user.user_id, "username": user.username, "is_admin": user.is_admin}}
