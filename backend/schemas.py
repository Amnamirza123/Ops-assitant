# schemas.py

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ApproveRequest(BaseModel):
    session_id: str
    approved: bool


class AddClientRequest(BaseModel):
    name: str
    email: str | None = None
    status: str = "active"
    notes: str | None = None
    role: str | None = None
    experience: str | None = None
    department: str | None = None
    salary: str | None = None

class RenameSessionRequest(BaseModel):
    title: str