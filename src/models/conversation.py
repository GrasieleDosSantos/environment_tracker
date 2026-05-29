from datetime import date, datetime

from pydantic import BaseModel, Field

from src.config.constants import Language


class ContextData(BaseModel):
    current_region: str | None = None
    current_biome: str | None = None
    current_state: str | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None
    language: Language = Language.PT


class ConversationMessage(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_context: dict | None = None
    langfuse_trace_id: str | None = None

    @property
    def is_user(self) -> bool:
        return self.role == "user"


class ConversationSession(BaseModel):
    session_id: str
    user_id: str | None = None
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    context_data: ContextData = Field(default_factory=ContextData)
    messages: list[ConversationMessage] = Field(default_factory=list)
    langfuse_session_id: str | None = None

    @property
    def query_count(self) -> int:
        return sum(1 for m in self.messages if m.is_user)

    def add_message(self, role: str, content: str, **kwargs: object) -> ConversationMessage:
        msg = ConversationMessage(role=role, content=content, **kwargs)  # type: ignore[arg-type]
        self.messages.append(msg)
        return msg

    def get_recent_messages(self, n: int = 10) -> list[ConversationMessage]:
        return self.messages[-n:]
