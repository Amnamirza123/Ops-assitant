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
    model="google/gemma-4-26b-a4b-it:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)

# Small, fast model for simple mechanical steps (classify, extraction) —
# these don't need heavy reasoning, just speed.
fast_llm = ChatOpenAI(
    model="nvidia/nemotron-3-nano-30b-a3b:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)
MAX_STEPS = 6


# ============================================================
# CLASSIFY
# ============================================================

def classify_node(state: AgentState) -> dict:
    question = state["messages"][-1].content

    forced_tool = state.get("forced_tool")

    # If the user picked a tool from the dropdown, skip the classify
    # LLM call entirely — we already know where to route.
    if forced_tool:
        return {
            "request_type": forced_tool,
            "next_tool": forced_tool,
            "original_question": question,
            "step_count": state.get("step_count", 0) + 1,
        }

    recent_messages = state["messages"][-6:]
    history_text = "\n".join(
        f"{m.type}: {m.content}" for m in recent_messages if hasattr(m, "content")
    )

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
        "an unrelated previous topic bias classification of a new, "
        "clearly different question.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Latest request:\n{question}\n\n"
        "Answer with only one word."
    )

    response = fast_llm.invoke(prompt)
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

    combined_prompt = (
        "From the request below, identify TWO things:\n"
        "1. The person/company name being asked about.\n"
        "2. Whether the request needs a math calculation AFTER getting "
        "their info (yes/no) — e.g. 'increase salary by 10%' needs math, "
        "'who is X' does not.\n\n"
        "Reply in exactly this format, nothing else:\n"
        "NAME: <name>\n"
        "MATH: <yes or no>\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"User request:\n{question}"
    )
    combined_response = llm.invoke(combined_prompt).content.strip()

    client_name = "unknown"
    math_needed = "no"
    for line in combined_response.split("\n"):
        if line.upper().startswith("NAME:"):
            client_name = line.split(":", 1)[1].strip()
        elif line.upper().startswith("MATH:"):
            math_needed = line.split(":", 1)[1].strip().lower()

        client = get_client_by_name(client_name, state["user_id"])

    if not client:
        return {
            "messages": [AIMessage(content=f"No client found matching '{client_name}'.")],
            "lookup_result": f"No client found matching '{client_name}'.",
            "client_data": None,
            "next_tool": None,
            "used_tool": "Client Lookup",
            "step_count": state.get("step_count", 0) + 1,
        }

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
        "used_tool": "Client Lookup",
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
        "the user's request, written as valid Python math syntax.\n\n"
        "Use numbers from the client information when necessary.\n\n"
        "Available: sin, cos, tan, sqrt, log, log10, exp, pi, e, "
        "radians(x), degrees(x), factorial, abs, round, pow.\n"
        "Trig functions use RADIANS — if the user gives degrees, wrap "
        "with radians(), e.g. 'sin 180 degrees' → sin(radians(180)).\n\n"
        "Examples:\n"
        "- 'increase salary by 10%' with salary 5000 → 5000 * 1.10\n"
        "- 'what is 20 + 30?' → 20 + 30\n"
        "- 'sin of 180 degrees' → sin(radians(180))\n"
        "- 'square root of 144' → sqrt(144)\n"
        "- 'pi times 10' → pi * 10\n\n"
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
        "used_tool": "Calculator",
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
        "used_tool": "Knowledge Base",
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
        "used_tool": None,
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
            "'general' means the user wants a brief, conversational description of "
            "the person — ONLY phrasings like 'who is X' or 'tell me about X'.\n\n"
            "'specific' means the user wants the actual data fields, including: "
            "a named field (email, salary, phone, role, department, experience, "
            "status), OR any phrasing that asks for their 'information', 'info', "
            "'details', or 'full details' — these should return the complete "
            "record, not a casual summary.\n\n"
            f"Request:\n{question}\n\n"
            "Answer with only one word."
        )
        intent = llm.invoke(intent_prompt).content.strip().lower()

        if intent == "specific" and not calculation_result:
            requested_fields_prompt = (
                "Identify exactly which fields the user requested.\n"
                "If the user asked for 'information', 'info', 'details', or "
                "'full details' (without naming specific fields), return ALL "
                "available field names.\n"
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

import re

def draft_email_node(state: AgentState) -> dict:
    if check_step_limit(state):
        return {
            "messages": [AIMessage(content="I've reached the maximum number of steps for this request. Please try rephrasing.")],
            "next_tool": None,
        }

    question = state.get("original_question") or state["messages"][-1].content

    # First, check if the message already contains a literal email address —
    # if so, use it directly, no client lookup needed.
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', question)

    if email_match:
        recipient_email = email_match.group(0)
        client = None  # no client record involved for a raw address
    else:
        name_prompt = (
            "Identify the person/company name this email should be sent to. "
            "Reply with ONLY the name.\n\n"
            f"Request:\n{question}"
        )
        recipient_name = llm.invoke(name_prompt).content.strip()
        client = get_client_by_name(recipient_name, state["user_id"])

        if not client or not client.get("email"):
            return {
                "messages": [AIMessage(content=f"Can't draft this email — no email on file for '{recipient_name}'. Add their email in the Clients panel first, or give me their email address directly.")],
                "next_tool": None,
            }
        recipient_email = client["email"]

    draft = draft_email.invoke(question)

    return {
        "draft_email": draft,
        "client_data": client or {"email": recipient_email},  # so send_email_node always has an email to use
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

import smtplib
from email.mime.text import MIMEText

def send_email_node(state: AgentState) -> dict:
    draft = state["draft_email"]
    client = state.get("client_data")
    recipient = client.get("email") if client else None

    if not recipient:
        return {
            "messages": [AIMessage(content="Could not send — no recipient email found for this client.")],
            "used_tool": "Email Assistant",
        }

    # Split subject line out of the draft (assumes "Subject: ..." as first line)
    lines = draft.strip().split("\n", 1)
    subject = lines[0].replace("Subject:", "").strip() if lines[0].lower().startswith("subject:") else "Message from Ops Assistant"
    body = lines[1].strip() if len(lines) > 1 else draft

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_EMAIL")
        msg["To"] = recipient

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("SMTP_EMAIL"), os.getenv("SMTP_PASSWORD"))
            server.sendmail(os.getenv("SMTP_EMAIL"), recipient, msg.as_string())

        return {
            "messages": [AIMessage(content=f"Email sent to {recipient}:\n\n{draft}")],
            "used_tool": "Email Assistant",
        }
    except Exception as e:
        return {
            "messages": [AIMessage(content=f"Failed to send email: {e}")],
            "used_tool": "Email Assistant",
        }


# ============================================================
# STOP
# ============================================================

def stop_node(state: AgentState) -> dict:
    return {
        "messages": [AIMessage(content="Email was not approved. No email was sent.")]
    }