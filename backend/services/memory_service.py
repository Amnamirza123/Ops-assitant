# services/memory_service.py

from services.supabase_service import supabase


def get_history(session_id: str, user_id: str) -> list[dict]:
    result = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .execute()
    )
    # Verify the session actually belongs to this user before returning
    # anything — chat_messages doesn't store user_id directly, so check
    # via chat_sessions.
    session_check = (
        supabase.table("chat_sessions")
        .select("session_id")
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not session_check.data:
        return []  # session doesn't belong to this user — return nothing

    return sorted(result.data, key=lambda m: m.get("created_at", ""))


def save_turn(session_id: str, user_id: str, user_message: str, assistant_message: str) -> None:
    # Make sure the session exists first (creates it on first message,
    # same idea as your old mongo_service.py's upsert behavior).
    existing = (
        supabase.table("chat_sessions")
        .select("session_id")
        .eq("session_id", session_id)
        .execute()
    )
    if not existing.data:
        supabase.table("chat_sessions").insert({
            "session_id": session_id,
            "user_id": user_id,
            "title": user_message[:50],
        }).execute()

    supabase.table("chat_messages").insert([
        {"session_id": session_id, "role": "user", "content": user_message},
        {"session_id": session_id, "role": "assistant", "content": assistant_message},
    ]).execute()


def list_user_sessions(user_id: str) -> list[dict]:
    result = (
        supabase.table("chat_sessions")
        .select("session_id, title")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def rename_session(session_id: str, user_id: str, title: str) -> bool:
    result = (
        supabase.table("chat_sessions")
        .update({"title": title})
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def delete_session(session_id: str, user_id: str) -> bool:
    result = (
        supabase.table("chat_sessions")
        .delete()
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0