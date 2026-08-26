from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    RESPONSE = "response"
    COMMAND = "command"

class SystemState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    AUTHENTICATING = "AUTHENTICATING"
    ERROR = "ERROR"


class Command(str, Enum):
    NONE = "NONE"
    FACE_AUTH = "FACE_AUTH"
    GET_TIME = "GET_TIME"
    GET_WEATHER = "GET_WEATHER"
    GET_LAB_INFO = "GET_LAB_INFO"
    END_CONVERSATION = "END_CONVERSATION"


class IntentSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=2000)

    context: dict[str, Any] | None = None


class CurlyResponse(BaseModel):
    type: ResponseType
    command: Command
    text: str

    state: CurlyState
    intent_source: IntentSource | None = None

class LLMDecision(BaseModel):
    type: ResponseType
    command: Command
    text: str
    confidence: float


class ChatResponse(CurlyResponse):
    session_id: str


# -----------------------------------------
# Android -> Curly events
# -----------------------------------------

class EventType(str, Enum):
    AUTH_RESULT = "AUTH_RESULT"
    WEATHER_RESULT = "WEATHER_RESULT"
    TIME_RESULT = "TIME_RESULT"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    STATE_UPDATE = "STATE_UPDATE"
    WAKE_WORD = "WAKE_WORD"
    LISTENING_STARTED = "LISTENING_STARTED"
    LISTENING_STOPPED = "LISTENING_STOPPED"
    TIMEOUT = "TIMEOUT"


class AuthStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNKNOWN_FACE = "UNKNOWN_FACE"
    NO_FACE = "NO_FACE"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    SERVER_ERROR = "SERVER_ERROR"


class EventRequest(BaseModel):
    session_id: str = Field(min_length=1)
    event: EventType
    data: dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    session_id: str
    type: ResponseType
    command: Command
    text: str

class TTSRequest(BaseModel):
    session_id: str = Field(
        min_length=1
    )

    text: str = Field(
        min_length=1,
        max_length=2000
    )

class STTResponse(BaseModel):
    text: str
    language: str
    language_probability: float

class SessionResponse(BaseModel):
    session_id: str
    active: bool

class CurlyState(str, Enum):
    IDLE = "IDLE"
    AWAKE="AWAKE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    AUTHENTICATING = "AUTHENTICATING"
    ERROR = "ERROR"