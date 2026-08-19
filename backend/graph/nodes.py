# graph/nodes.py

import os
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from services.supabase_service import get_client_by_name
from graph.state import AgentState

from tools.calculator_tool import calculator
from tools.rag_tool import run_rag_search
from tools.email_tool import draft_email


llm = ChatOpenAI(
    model="nvidia/nemotron-3.5-lightning:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)

MAX_STEPS = 6


# ============================================================
# CLASSIFY
# ============================================================

def classify_node(state: AgentState) -> dict:
    recent_messages = state["messages"][-6:]
    history_text = "\n".join(
        f"{m.type}: {m.content}" for m in recent_messages if hasattr(m, "content")
    )
    question = state["messages"][-1].content

    prompt = (
        "Classify the LATEST user request into exactly one word: "
        "'math', 'client', 'email', 'rag', or 'general'.\n\n"
        "- 'math' for calculations or mathematical operations.\n"
        "- 'client' for questions about a specific person or company, "
        "including their name, status, account, email, role, department, "
        "experience, salary, phone, or contact information.\n"
        "- 'email' for drafting or sending an email.\n"
        "- 'rag' for questions about internal documents, schedules, "
        "policies, weeks, procedures, or other document knowledge.\n"
        "- 'general' for normal conversation, greetings, or unrelated "
        "small talk.\n\n"
        "If a request contains both client information and a calculation, "
        "prefer 'client' first so the client information can be retrieved "
        "before the calculation is performed.\n\n"
        "IMPORTANT: base your classification primarily on the LATEST "
        "request text itself. Only use the recent conversation to "
        "resolve ambiguous pronouns like 'her'/'it'/'that' — do NOT let "
        "an unrelated previous topic (like a prior math question) bias "
        "classification of a new, clearly different question.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Latest request:\n{question}\n\n"
        "Answer with only one word."
    )

    response = llm.invoke(prompt)
    request_type = response.content.strip().lower()

    allowed = {"math", "client", "email", "rag", "general"}
    if request_type not in allowed:
        request_type = "general"

    return {
        "request_type": request_type,
        "next_tool": request_type,
        "original_question": question,
        "step_count": state.get("step_count", 0) + 1,
    }


# ============================================================
# STEP LIMIT
# ============================================================

def check_step_limit(state: AgentState) -> bool:
    return state.get("step_count", 0) >= MAX_STEPS


# ============================================================
# CLIENT LOOKUP
# ============================================================

def lookup_node(state: AgentState) -> dict:
    if check_step_limit(state):
        return {
            "messages": [AIMessage(content="I've reached the maximum number of steps for this request. Please try rephrasing.")],
            "next_tool": None,
        }

    recent_messages = state["messages"][-6:]
    history_text = "\n".join(
        f"{m.type}: {m.content}" for m in recent_messages if hasattr(m, "content")
    )
    question = state.get("original_question") or state["messages"][-1].content

    extract_prompt = (
        "Based on the user's request and recent conversation, identify "
        "the person or company being asked about.\n"
        "Reply with ONLY the person/company name.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"User request:\n{question}"
    )
    client_name = llm.invoke(extract_prompt).content.strip()

    client = get_client_by_name(client_name)

    if not client:
        return {
            "messages": [AIMessage(content=f"No client found matching '{client_name}'.")],
            "lookup_result": f"No client found matching '{client_name}'.",
            "client_data": None,
            "next_tool": None,
            "step_count": state.get("step_count", 0) + 1,
        }

    math_check_prompt = (
        "Determine whether the user's request requires a mathematical "
        "calculation AFTER retrieving the client information.\n\n"
        "Return exactly one word: 'yes' or 'no'.\n\n"
        f"User request:\n{question}\n\n"
        f"Client information:\n{json.dumps(client, default=str)}"
    )
    math_needed = llm.invoke(math_check_prompt).content.strip().lower()

    safe_fields = {
        k: v for k, v in {
            "name": client.get("name"),
            "email": client.get("email"),
            "status": client.get("status"),
            "role": client.get("role"),
            "department": client.get("department"),
            "experience": client.get("experience"),
            "salary": client.get("salary"),
            "notes": client.get("notes"),
        }.items() if v is not None and v != ""
    }
    lookup_result = json.dumps(safe_fields, indent=2, default=str)

    next_tool = "calculator" if math_needed == "yes" else "final"

    return {
        "client_data": client,
        "lookup_result": lookup_result,
        "next_tool": next_tool,
        "step_count": state.get("step_count", 0) + 1,
    }


# ============================================================
# CALCULATOR
# ============================================================

def calculator_node(state: AgentState) -> dict:
    if check_step_limit(state):
        return {
            "messages": [AIMessage(content="I've reached the maximum number of steps for this request. Please try rephrasing.")],
            "next_tool": None,
        }

    question = state.get("original_question") or state["messages"][-1].content
    client = state.get("client_data")
    client_context = ""
    if client:
        client_context = f"\n\nClient information available:\n{json.dumps(client, default=str)}"

    extract_prompt = (
        "Extract ONLY the mathematical expression needed to answer "
        "the user's request.\n\n"
        "Use numbers from the client information when necessary.\n\n"
        "Examples:\n"
        "- 'increase salary by 10%' with salary 5000 → 5000 * 1.10\n"
        "- 'decrease salary by 20%' with salary 5000 → 5000 * 0.80\n"
        "- 'what is 20 + 30?' → 20 + 30\n\n"
        "Return ONLY the expression. Do not include words, explanation, or markdown.\n\n"
        f"User request:\n{question}"
        f"{client_context}"
    )
    expression = llm.invoke(extract_prompt).content.strip()
    expression = expression.replace("```", "").strip()

    result = calculator.invoke(expression)

    return {
        "calculation_result": str(result),
        "next_tool": "final",
        "step_count": state.get("step_count", 0) + 1,
    }


# ============================================================
# RAG
# ============================================================

def rag_node(state: AgentState) -> dict:
    if check_step_limit(state):
        return {
            "messages": [AIMessage(content="I've reached the maximum number of steps for this request. Please try rephrasing.")],
            "next_tool": None,
        }

    recent_messages = state["messages"][-6:]
    history_text = "\n".join(
        f"{m.type}: {m.content}" for m in recent_messages if hasattr(m, "content")
    )
    raw_question = state.get("original_question") or state["messages"][-1].content

    # Rewrite vague follow-ups into standalone questions using recent
    # history, same technique as docuchat's Day 2 RAG memory.
    rewrite_prompt = (
        "Given this recent conversation, rewrite the LATEST message into "
        "a standalone question that makes sense without needing the "
        "history. If it's already standalone, return it unchanged.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Latest message:\n{raw_question}"
    )
    standalone_question = llm.invoke(rewrite_prompt).content.strip()

    result = run_rag_search(standalone_question, state["session_id"])

    return {
        "rag_result": str(result),
        "next_tool": "final",
        "step_count": state.get("step_count", 0) + 1,
    }

# ============================================================
# GENERAL
# ============================================================

def general_node(state: AgentState) -> dict:
    recent = state["messages"][-2:]
    response = llm.invoke(recent)
    return {
        "messages": [response],
        "next_tool": None,
    }


# ============================================================
# FINAL SYNTHESIS
# ============================================================

def final_node(state: AgentState) -> dict:
    question = state.get("original_question", "")
    client_data = state.get("client_data")
    calculation_result = state.get("calculation_result")
    rag_result = state.get("rag_result")

    if client_data:
        intent_prompt = (
            "Classify the user's request into exactly one word: 'general' or 'specific'.\n\n"
            "'general' means the user wants a conversational description of the "
            "person, such as 'who is Khadija' or 'tell me about Khadija'.\n\n"
            "'specific' means the user asks for particular fields such as email, "
            "salary, phone, role, department, experience, status, or details.\n\n"
            f"Request:\n{question}\n\n"
            "Answer with only one word."
        )
        intent = llm.invoke(intent_prompt).content.strip().lower()

        if intent == "specific" and not calculation_result:
            requested_fields_prompt = (
                "Identify exactly which fields the user requested.\n"
                "Return only the field names separated by commas.\n\n"
                "Available fields:\n"
                "name, email, status, role, department, experience, salary, notes\n\n"
                f"Request:\n{question}"
            )
            requested_fields = llm.invoke(requested_fields_prompt).content.strip().lower()
            fields = [f.strip() for f in requested_fields.split(",")]

            output = []
            for field in fields:
                if field in client_data:
                    value = client_data.get(field)
                    if value is not None and value != "":
                        output.append(f"{field}: {value}")

            if output:
                return {
                    "messages": [AIMessage(content="\n".join(output))],
                    "next_tool": None,
                }

                # Strip sensitive fields BEFORE the LLM ever sees them for the
        # general case — a structural guarantee, not a prompt request
        # the model could ignore.
        safe_client_data = {
            k: v for k, v in client_data.items()
            if k not in ("email", "salary")
        }

                # Strip sensitive fields BEFORE the LLM ever sees them for the
        # general case — a structural guarantee, not a prompt request
        # the model could ignore.
        safe_client_data = {
            k: v for k, v in client_data.items()
            if k not in ("email", "salary")
        }

        # Strip sensitive fields BEFORE the LLM ever sees them for the
        # general case — a structural guarantee, not a prompt request
        # the model could ignore.
        safe_client_data = {
            k: v for k, v in client_data.items()
            if k not in ("email", "salary")
        }

        synthesis_prompt = (
            "Answer the user's request using ONLY the information provided below.\n\n"
            "If the user asks a casual/general question about the client, respond "
            "naturally in a short readable paragraph.\n"
            "Do not say 'according to the record'.\n"
            "Do not invent information.\n"
            "If a calculation result is provided, include the result naturally "
            "in the answer.\n\n"
            f"User request:\n{question}\n\n"
            f"Client information:\n{json.dumps(safe_client_data, default=str)}\n\n"
            f"Calculation result:\n{calculation_result or 'None'}"
        )
        response = llm.invoke(synthesis_prompt)

        return {
            "messages": [response],
            "next_tool": None,
        }

    if rag_result:
        return {
            "messages": [AIMessage(content=rag_result)],
            "next_tool": None,
        }

    if calculation_result:
        return {
            "messages": [AIMessage(content=calculation_result)],
            "next_tool": None,
        }

    return {"next_tool": None}


# ============================================================
# EMAIL
# ============================================================

def draft_email_node(state: AgentState) -> dict:
    if check_step_limit(state):
        return {
            "messages": [AIMessage(content="I've reached the maximum number of steps for this request. Please try rephrasing.")],
            "next_tool": None,
        }

    question = state.get("original_question") or state["messages"][-1].content
    draft = draft_email.invoke(question)

    return {
        "draft_email": draft,
        "step_count": state.get("step_count", 0) + 1,
    }


# ============================================================
# HUMAN APPROVAL
# ============================================================

def wait_for_approval_node(state: AgentState) -> dict:
    decision = interrupt({
        "message": "Approve sending this email?",
        "draft_email": state["draft_email"],
    })
    return {"approved": decision}


# ============================================================
# SEND EMAIL
# ============================================================

def send_email_node(state: AgentState) -> dict:
    return {
        "messages": [AIMessage(content=f"Email sent:\n\n{state['draft_email']}")]
    }


# ============================================================
# STOP
# ============================================================

def stop_node(state: AgentState) -> dict:
    return {
        "messages": [AIMessage(content="Email was not approved. No email was sent.")]
    }