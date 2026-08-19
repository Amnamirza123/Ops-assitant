# graph/build_graph.py

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from graph.state import AgentState

from graph.nodes import (
    classify_node,
    calculator_node,
    lookup_node,
    rag_node,
    general_node,
    final_node,
    draft_email_node,
    wait_for_approval_node,
    send_email_node,
    stop_node,
)


# ============================================================
# ROUTE AFTER CLASSIFICATION
# ============================================================

def route_after_classify(state: AgentState) -> str:

    request_type = state.get("request_type")

    if request_type == "math":
        return "calculator"

    elif request_type == "client":
        return "lookup"

    elif request_type == "rag":
        return "rag"

    elif request_type == "email":
        return "draft_email"

    return "general"


# ============================================================
# ROUTE AFTER A TOOL
# ============================================================

def route_after_tool(state: AgentState) -> str:

    next_tool = state.get("next_tool")

    if next_tool == "calculator":
        return "calculator"

    elif next_tool == "lookup":
        return "lookup"

    elif next_tool == "rag":
        return "rag"

    elif next_tool == "general":
        return "general"

    elif next_tool == "final":
        return "final"

    return "end"


# ============================================================
# ROUTE AFTER APPROVAL
# ============================================================

def route_after_approval(state: AgentState) -> str:

    return (
        "send_email"
        if state.get("approved")
        else "stop"
    )


# ============================================================
# BUILD GRAPH
# ============================================================

graph_builder = StateGraph(AgentState)


# ------------------------------------------------------------
# Nodes
# ------------------------------------------------------------

graph_builder.add_node(
    "classify",
    classify_node,
)

graph_builder.add_node(
    "calculator",
    calculator_node,
)

graph_builder.add_node(
    "lookup",
    lookup_node,
)

graph_builder.add_node(
    "rag",
    rag_node,
)

graph_builder.add_node(
    "general",
    general_node,
)

graph_builder.add_node(
    "final",
    final_node,
)

graph_builder.add_node(
    "draft_email",
    draft_email_node,
)

graph_builder.add_node(
    "wait_for_approval",
    wait_for_approval_node,
)

graph_builder.add_node(
    "send_email",
    send_email_node,
)

graph_builder.add_node(
    "stop",
    stop_node,
)


# ============================================================
# START → CLASSIFY
# ============================================================

graph_builder.add_edge(
    START,
    "classify",
)


# ============================================================
# CLASSIFY → FIRST TOOL
# ============================================================

graph_builder.add_conditional_edges(
    "classify",
    route_after_classify,
)


# ============================================================
# TOOL → NEXT TOOL / FINAL
# ============================================================

tool_routes = {
    "calculator": "calculator",
    "lookup": "lookup",
    "rag": "rag",
    "general": "general",
    "final": "final",
    "end": END,
}


graph_builder.add_conditional_edges(
    "lookup",
    route_after_tool,
    tool_routes,
)

graph_builder.add_conditional_edges(
    "calculator",
    route_after_tool,
    tool_routes,
)

graph_builder.add_conditional_edges(
    "rag",
    route_after_tool,
    tool_routes,
)


# ============================================================
# GENERAL → END
# ============================================================

graph_builder.add_edge(
    "general",
    END,
)


# ============================================================
# FINAL → END
# ============================================================

graph_builder.add_edge(
    "final",
    END,
)


# ============================================================
# EMAIL WORKFLOW
# ============================================================

graph_builder.add_edge(
    "draft_email",
    "wait_for_approval",
)

graph_builder.add_conditional_edges(
    "wait_for_approval",
    route_after_approval,
)


graph_builder.add_edge(
    "send_email",
    END,
)


graph_builder.add_edge(
    "stop",
    END,
)


# ============================================================
# CHECKPOINTER
# ============================================================

# InMemorySaver is fine for the Week 4 project.
# It will lose paused state if the server restarts.

checkpointer = InMemorySaver()


graph = graph_builder.compile(
    checkpointer=checkpointer
)