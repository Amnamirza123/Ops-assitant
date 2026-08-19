# tools/client_lookup_tool.py

from langchain_core.tools import tool
from services.supabase_service import get_client_by_name


@tool
def client_lookup(client_name: str) -> str:
    """Looks up a client's account status, email, and notes by their
    company name. Use this when the user asks about a specific client's
    account, status, or contact info. Input should be the client's
    company name as it would appear in records, e.g. 'Acme Corp'.
    """
    client = get_client_by_name(client_name)

    if not client:
        return f"No client found matching '{client_name}'."

    return (
        f"Client: {client['name']}\n"
        f"Email: {client.get('email', 'N/A')}\n"
        f"Status: {client.get('status', 'N/A')}\n"
        f"Notes: {client.get('notes', 'N/A')}"
    )