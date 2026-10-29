from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from supabase import Client, create_client

from .config import Settings, get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


def _client(settings: Settings) -> Client:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured.")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_current_user(request: Request, settings: Settings = Depends(get_settings)) -> AuthenticatedUser:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="A valid Supabase bearer token is required.")
    try:
        user = _client(settings).auth.get_user(token).user
    except Exception as exc:
        raise HTTPException(status_code=401, detail="The Supabase access token is invalid or expired.") from exc
    if not user:
        raise HTTPException(status_code=401, detail="The Supabase access token is invalid or expired.")
    return AuthenticatedUser(id=user.id, email=getattr(user, "email", None))
