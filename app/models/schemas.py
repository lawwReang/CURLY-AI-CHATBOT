from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =========================================================
# RESPONSE / STATE ENUMS
# =========================================================

class ResponseType(str, Enum):
    RESPONSE = "response"
    COMMAND = "command"


class CurlyState(str, Enum):
    IDLE = "IDLE"
    AWAKE = "AWAKE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    AUTHENTICATING = "AUTHENTICATING"
    ERROR = "ERROR"


# Keep this for compatibility with any code that imports it.
class SystemState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    AUTHENTICATING = "AUTHENTICATING"
    ERROR = "ERROR"


# =========================================================
# COMMANDS
# =========================================================

class Command(str, Enum):
    NONE = "none"

    # Authentication
    FACE_AUTH = "face_auth"

    # Time / date / weather
    GET_TIME = "get_time"

    GET_DATE = "get_date"

    GET_WEATHER = "get_weather"

    # General lab information
    GET_LAB_INFO = "get_lab_info"

    # Specific lab information
    GET_LAB_IN_CHARGE = "get_lab_in_charge"
    GET_LAB_NODAL_OFFICER = "get_lab_nodal_officer"
    GET_LAB_HOURS = "get_lab_hours"
    GET_LAB_LOCATION = "get_lab_location"
    GET_LAB_CONTACT = "get_lab_contact"
    GET_LAB_EMAIL = "get_lab_email"

    # Conversation
    END_CONVERSATION = "end_conversation"


# =========================================================
# INTENT
# =========================================================

class IntentSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


# =========================================================
# CHAT
# =========================================================

class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=1
    )

    text: str = Field(
        min_length=1,
        max_length=2000
    )

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


# =========================================================
# ANDROID -> CURLY EVENTS
# =========================================================

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
    session_id: str = Field(
        min_length=1
    )

    event: EventType

    data: dict[str, Any] = Field(
        default_factory=dict
    )


class EventResponse(BaseModel):
    session_id: str
    type: ResponseType
    command: Command
    text: str


# =========================================================
# TTS / STT
# =========================================================

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


# =========================================================
# SESSION
# =========================================================

class SessionResponse(BaseModel):
    session_id: str
    active: bool