# tools/rag_tool.py

import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from services.supabase_service import supabase

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

llm = ChatOpenAI(
    model="nvidia/nemotron-3.5-lightning:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)


def search_knowledge_base(question: str, session_id: str, k: int = 8) -> list[dict]:
    query_embedding = embeddings.embed_query(question)

    result = supabase.rpc(
        "match_kb_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": k,
            "filter_session_id": session_id,  # ADDED — scopes search to this session
        },
    ).execute()

    return result.data


answer_prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer using ONLY the following context from company documents. "
               "Pay close attention to which week/day the question asks about — "
               "the context may contain content from multiple weeks; only use "
               "content that specifically matches the week/day requested. "
               "If the context doesn't contain that exact week/day, say so "
               "explicitly rather than answering from a different week.\n\n{context}"),
    ("human", "{question}"),
])


# NOTE: this is no longer decorated with @tool directly, since it now
# needs session_id — see rag_node in graph/nodes.py, which calls
# search_knowledge_base() and this answer logic directly instead of
# going through .invoke() on a standalone tool object.
def run_rag_search(question: str, session_id: str) -> str:
    chunks = search_knowledge_base(question, session_id)

    if not chunks:
        return "No relevant information found in the knowledge base for this conversation."

    context = "\n\n".join(c["content"] for c in chunks)
    chain = answer_prompt | llm
    response = chain.invoke({"context": context, "question": question})
    return response.content