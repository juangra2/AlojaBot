# Modelos Pydantic de entrada/salida de /chat

from pydantic import BaseModel

class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


class ChatOut(BaseModel):
    answer: str | None = None
    evidence: list | None = None
    candidatos: list | None = None
    weather: str | None = None
