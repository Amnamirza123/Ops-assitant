# services/supabase_service.py

import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---- Client records ----

def get_client_by_name(name: str) -> dict | None:
    result = (
        supabase.table("clients")
        .select("*")
        .ilike("name", f"%{name}%")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def list_clients() -> list[dict]:
    result = supabase.table("clients").select("*").order("created_at", desc=True).execute()
    return result.data


def add_client(
    name: str,
    email: str | None,
    status: str,
    notes: str | None,
    role: str | None = None,
    experience: str | None = None,
    department: str | None = None,
    salary: str | None = None,
) -> dict:
    result = (
        supabase.table("clients")
        .insert({
            "name": name,
            "email": email,
            "status": status,
            "notes": notes,
            "role": role,
            "experience": experience,
            "department": department,
            "salary": salary,
        })
        .execute()
    )
    return result.data[0]


def bulk_add_clients(rows: list[dict]) -> int:
    if not rows:
        return 0
    result = supabase.table("clients").insert(rows).execute()
    return len(result.data)


def delete_client(client_id: str) -> bool:
    result = supabase.table("clients").delete().eq("id", client_id).execute()
    return len(result.data) > 0


# ---- Knowledge base documents (session-scoped) ----

def document_exists(filename: str, session_id: str) -> bool:
    result = (
        supabase.table("kb_documents")
        .select("id")
        .eq("filename", filename)
        .eq("session_id", session_id)
        .execute()
    )
    return len(result.data) > 0


def list_documents(user_id: str, session_id: str) -> list[dict]:
    result = (
        supabase.table("kb_documents")
        .select("*")
        .eq("user_id", user_id)
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def delete_document(document_id: str, user_id: str) -> bool:
    result = (
        supabase.table("kb_documents")
        .delete()
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0