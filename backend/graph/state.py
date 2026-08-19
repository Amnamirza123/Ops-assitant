# graph/state.py

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # The running conversation, including tool calls and results.
    # add_messages appends new messages instead of replacing the list.
    messages: Annotated[list, add_messages]

    session_id: str
    user_id: str

    # Original user request for the current graph run.
    # This must stay available even after tools add messages.
    original_question: Optional[str]

    # Set by classify.
    request_type: Optional[str]
    # "math" | "client" | "email" | "rag" | "general"

    # The next tool/node that should run.
    next_tool: Optional[str]

    # Which tool actually produced the final answer — shown in the UI
    # as a small badge on each response.
    used_tool: Optional[str]

    # Information retrieved from the client lookup.
    client_data: Optional[dict]

    # Result produced by calculator.
    calculation_result: Optional[str]

    # Result produced by RAG.
    rag_result: Optional[str]

    # Result produced by client lookup.
    lookup_result: Optional[str]

    # Holds the drafted email while waiting for approval.
    draft_email: Optional[str]

    # None = still waiting; True/False once a human responds.
    approved: Optional[bool]

    # Guardrail tracking.
    step_count: int