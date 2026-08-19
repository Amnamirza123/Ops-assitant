# services/auth_dependency.py

from fastapi import Header, HTTPException
from services.supabase_service import supabase


def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")

    token = authorization.split(" ", 1)[1]

    try:
        # Supabase verifies the JWT itself and returns the user it belongs to.
        # This replaces our old manual jwt.decode() + JWT_SECRET check —
        # Supabase Auth issued the token, so Supabase Auth verifies it.
        response = supabase.auth.get_user(token)
        user = response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"user_id": user.id, "email": user.email}