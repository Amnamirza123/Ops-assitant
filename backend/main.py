# main.py

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from services.memory_service import save_turn  
from fastapi.responses import StreamingResponse
from fastapi import Form

from schemas import ChatRequest, ApproveRequest, AddClientRequest, RenameSessionRequest
from graph.build_graph import graph
from services.auth_dependency import get_current_user
from services.supabase_service import add_client, list_clients, delete_client, bulk_add_clients, list_documents, delete_document
from services.memory_service import get_history, list_user_sessions, rename_session, delete_session
from services.client_import_service import parse_client_file
from services.document_service import process_document

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok"}


# ---- Agent chat ----



@app.post("/chat")
def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    config = {"configurable": {"thread_id": request.session_id}}

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=request.message)],
            "session_id": request.session_id,
            "user_id": user["user_id"],
            "step_count": 0,
        },
        config=config,
    )

    if "__interrupt__" in result:
        interrupt_obj = result["__interrupt__"][0]
        return {"status": "waiting_for_approval", "details": interrupt_obj.value}

    answer = result["messages"][-1].content
    used_tool = result.get("used_tool")
    save_turn(request.session_id, user["user_id"], request.message, answer)
    return {"status": "done", "answer": answer, "used_tool": used_tool}

@app.post("/approve")
def approve(request: ApproveRequest, user: dict = Depends(get_current_user)):
    config = {"configurable": {"thread_id": request.session_id}}
    result = graph.invoke(Command(resume=request.approved), config=config)
    answer = result["messages"][-1].content
    save_turn(request.session_id, user["user_id"], "[approval decision]", answer)  # ADD THIS
    return {"status": "done", "answer": answer}
# ---- Chat sessions (sidebar) ----

@app.get("/chat/sessions")
def sessions(user: dict = Depends(get_current_user)):
    return list_user_sessions(user["user_id"])


@app.get("/chat/{session_id}/history")
def history(session_id: str, user: dict = Depends(get_current_user)):
    return get_history(session_id, user["user_id"])


@app.patch("/chat/{session_id}/rename")
def rename(session_id: str, request: RenameSessionRequest, user: dict = Depends(get_current_user)):
    success = rename_session(session_id, user["user_id"], request.title)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "title": request.title}


@app.delete("/chat/{session_id}")
def delete(session_id: str, user: dict = Depends(get_current_user)):
    success = delete_session(session_id, user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# ---- Clients ----

@app.get("/clients")
def get_clients(user: dict = Depends(get_current_user)):
    return list_clients()


@app.post("/clients")
def create_client(request: AddClientRequest, user: dict = Depends(get_current_user)):
    return add_client(request.name, request.email, request.status, request.notes, request.role, request.experience, request.department, request.salary)


@app.delete("/clients/{client_id}")
def remove_client(client_id: str, user: dict = Depends(get_current_user)):
    success = delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"deleted": True}


@app.post("/clients/import")
async def import_clients(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    rows = await parse_client_file(file)
    count = bulk_add_clients(rows)
    return {"imported": count}


# ---- Knowledge base documents ----

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), session_id: str = Form(...), user: dict = Depends(get_current_user)):
    result = await process_document(file, user["user_id"], session_id)
    return result

@app.get("/documents")
def get_documents(session_id: str, user: dict = Depends(get_current_user)):
    return list_documents(user["user_id"], session_id)

@app.delete("/documents/{document_id}")
def remove_document(document_id: str, user: dict = Depends(get_current_user)):
    success = delete_document(document_id, user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}

@app.get("/chat/{session_id}/pending-approval")
def get_pending_approval(session_id: str, user: dict = Depends(get_current_user)):
    config = {"configurable": {"thread_id": session_id}}
    state = graph.get_state(config)
    if state.next and state.tasks:
        interrupt_value = state.tasks[0].interrupts[0].value
        return interrupt_value
    return {"draft_email": None}

