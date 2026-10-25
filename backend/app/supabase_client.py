from supabase import Client, create_client
from .config import Settings


def build_supabase(settings: Settings) -> Client | None:
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_anon_key)
