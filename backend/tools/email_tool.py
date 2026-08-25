# tools/email_tool.py

import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

llm = ChatOpenAI(
    model="nvidia/llama-nemotron-rerank-vl-1b-v2:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0.3,  # slightly higher — drafting benefits from a little natural variation
)


@tool
def draft_email(request: str) -> str:
    """Drafts a professional email based on the user's request. Use this
    when the user asks to write, draft, or send an email to someone.
    This tool ONLY creates a draft — it does not send anything. Sending
    always requires separate human approval after this tool runs.
    Input should describe who the email is for and what it should say.
    """
    prompt = (
        "Draft a short, professional email based on this request. "
        "Include a subject line and body. Do not include placeholder "
        "brackets like [Name] if the actual name is available in the request.\n\n"
        f"Request: {request}"
    )
    response = llm.invoke(prompt)
    return response.content